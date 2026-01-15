'''
Description: PDF 文件的加密与去密
Version: 3.0 (高性能多进程版)
Author: Glenn
Email: chenluda01@outlook.com
Date: 2023-05-15 14:07:20
Copyright (c) 2023 by Kust-BME, All Rights Reserved. 

优化策略：
1. PDF文件预加载到内存，避免重复磁盘I/O
2. 多进程并行处理，充分利用多核CPU
3. 批量密码验证，减少进程间通信开销
4. 密码列表优化（去重、排序）
5. 早期退出机制
'''
import pikepdf
import os
import argparse
import time
import signal
import sys
from io import BytesIO
from multiprocessing import Pool

# 尝试导入 pyhanko（用于提取 PDF hash）
try:
    from pyhanko.pdf_utils.misc import PdfReadError
    from pyhanko.pdf_utils.reader import PdfFileReader
    PYHANKO_AVAILABLE = True
except ImportError:
    PYHANKO_AVAILABLE = False

def verify_password_in_memory(pdf_data, password):
    """
    在内存中验证PDF密码，避免磁盘I/O
    
    参数:
        pdf_data: PDF文件的二进制数据
        password: 要验证的密码
        
    返回:
        bool: 密码是否正确
    """
    try:
        pdf = pikepdf.open(BytesIO(pdf_data), password=password)
        pdf.close()
        return True
    except (pikepdf.PasswordError, pikepdf.PdfError):
        return False
    except Exception:
        # 其他异常也视为密码错误
        return False


def verify_password_batch(pdf_data, password_batch):
    """
    批量验证密码，返回第一个成功的密码
    
    参数:
        pdf_data: PDF文件的二进制数据
        password_batch: 密码批次（列表）
        
    返回:
        str or None: 第一个成功的密码，如果没有则返回None
    """
    for password in password_batch:
        if verify_password_in_memory(pdf_data, password):
            return password
    return None


def verify_password_worker(args):
    """
    工作进程函数：验证一批密码
    
    参数:
        args: (pdf_data, password_batch) 元组
        
    返回:
        str or None: 找到的密码，如果没有则返回None
    """
    # 在子进程中忽略 KeyboardInterrupt，避免输出 Traceback
    import signal
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    
    try:
        pdf_data, password_batch = args
        return verify_password_batch(pdf_data, password_batch)
    except KeyboardInterrupt:
        # 子进程中的中断，静默处理
        return None
    except Exception:
        # 其他异常也静默处理
        return None


def load_passwords_from_dict(dictionary_folder):
    """
    从字典文件夹加载所有密码，并进行优化处理
    
    参数:
        dictionary_folder: 字典文件夹路径
        
    返回:
        list: 优化后的密码列表（去重、排序）
    """
    all_passwords = []
    
    # 收集所有密码
    for root, _, files in os.walk(dictionary_folder):
        for file in files:
            if file.endswith('.txt'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        for line in f:
                            password = line.strip()
                            if password:  # 忽略空行
                                all_passwords.append(password)
                except Exception as e:
                    print(f"⚠️ 读取字典文件失败 {file_path}: {e}")
                    continue
    
    if not all_passwords:
        return []
    
    # 去重（保持顺序）
    unique_passwords = list(dict.fromkeys(all_passwords))
    
    # 优化排序：短密码优先，然后按字典序
    sorted_passwords = sorted(unique_passwords, key=lambda x: (len(x), x))
    
    print(f"📚 加载密码字典：原始 {len(all_passwords)} 个，去重后 {len(unique_passwords)} 个")
    
    return sorted_passwords


def crack_pdf_password_optimized(input_file, dictionary_folder, num_processes=8, batch_size=50):
    """
    高性能PDF密码破解（多进程版本）
    
    参数:
        input_file: PDF文件路径
        dictionary_folder: 密码字典文件夹路径
        num_processes: 进程数（默认8）
        batch_size: 每个进程处理的密码批次大小（默认50）
        
    返回:
        str: 找到的密码
        None: 未找到密码或用户中断
    """
    start_time = time.time()
    
    # 1. 预加载PDF到内存
    print("📥 预加载PDF文件到内存...")
    try:
        with open(input_file, 'rb') as f:
            pdf_data = f.read()
        print(f"✅ PDF文件已加载到内存 ({len(pdf_data) / 1024:.2f} KB)")
    except Exception as e:
        print(f"❌ 加载PDF文件失败: {e}")
        return None
    
    # 2. 加载并优化密码列表
    print("📚 加载密码字典...")
    passwords = load_passwords_from_dict(dictionary_folder)
    
    if not passwords:
        print("❌ 字典中没有找到有效密码")
        return None
    
    print(f"🚀 开始破解，使用 {num_processes} 个进程，批次大小 {batch_size}")
    
    # 3. 将密码列表分批
    password_batches = []
    for i in range(0, len(passwords), batch_size):
        batch = passwords[i:i + batch_size]
        password_batches.append((pdf_data, batch))
    
    print(f"📦 共分为 {len(password_batches)} 个批次")
    
    # 4. 多进程并行验证
    found_password = None
    completed_batches = 0
    last_progress_time = start_time
    pool = None
    
    # 设置信号处理，快速终止子进程
    def signal_handler(sig, frame):
        # 立即终止进程池，减少子进程的错误输出
        if pool is not None:
            try:
                pool.terminate()
                # 不等待，立即继续
            except:
                pass
        raise KeyboardInterrupt
    
    original_handler = signal.signal(signal.SIGINT, signal_handler)
    
    try:
        pool = Pool(num_processes)
        # 使用imap_unordered以获得更好的性能（不保证顺序）
        results = pool.imap_unordered(verify_password_worker, password_batches)
        
        # 处理结果，找到密码后立即返回
        try:
            for result in results:
                completed_batches += 1
                tried_count = min(completed_batches * batch_size, len(passwords))
                
                if result is not None:
                    found_password = result
                    elapsed_time = time.time() - start_time
                    speed = tried_count / elapsed_time if elapsed_time > 0 else 0
                    print(f"\n✅ 找到密码：{found_password}")
                    print(f"📊 性能：{speed:.2f} 密码/秒 (耗时：{elapsed_time:.2f}秒)")
                    print(f"📈 尝试了约 {tried_count} 个密码")
                    
                    # 终止所有进程
                    pool.terminate()
                    pool.join()
                    return found_password
                
                # 每1秒或每100个批次输出一次进度
                current_time = time.time()
                if current_time - last_progress_time >= 1.0 or completed_batches % 100 == 0:
                    elapsed_time = current_time - start_time
                    speed = tried_count / elapsed_time if elapsed_time > 0 else 0
                    progress_pct = (tried_count / len(passwords) * 100) if len(passwords) > 0 else 0
                    print(f"⏳ 进度: {tried_count}/{len(passwords)} ({progress_pct:.1f}%), 速度: {speed:.2f} 密码/秒", end='\r')
                    last_progress_time = current_time
        except KeyboardInterrupt:
            # 立即终止进程池，减少子进程的错误输出
            if pool is not None:
                try:
                    pool.terminate()
                    # 不等待，立即继续
                except:
                    pass
            raise  # 重新抛出，让外层处理
    
    except KeyboardInterrupt:
        elapsed_time = time.time() - start_time
        tried_count = completed_batches * batch_size
        speed = tried_count / elapsed_time if elapsed_time > 0 else 0
        print(f"\n\n⚠️ 用户中断（Ctrl+C）")
        print(f"📊 已尝试: {tried_count} 个密码")
        print(f"📊 速度: {speed:.2f} 密码/秒 (耗时: {elapsed_time:.2f}秒)")
        if len(passwords) > 0:
            progress_pct = (tried_count / len(passwords) * 100)
            print(f"📉 进度: {tried_count}/{len(passwords)} ({progress_pct:.1f}%)")
        # 确保进程池被终止
        if pool is not None:
            try:
                pool.terminate()
                # 快速清理，不等待子进程完全结束
            except:
                pass
        # 恢复原始信号处理
        signal.signal(signal.SIGINT, original_handler)
        # 返回特殊值表示用户中断
        raise KeyboardInterrupt("用户中断破解过程")
    except Exception as e:
        print(f"\n❌ 破解过程出错: {e}")
        if pool is not None:
            try:
                pool.terminate()
                pool.join()
            except:
                pass
        return None
    finally:
        # 确保进程池被正确关闭
        if pool is not None:
            try:
                pool.close()
                pool.join()
            except:
                pass
    
    # 5. 如果没找到密码
    elapsed_time = time.time() - start_time
    speed = len(passwords) / elapsed_time if elapsed_time > 0 else 0
    print(f"\n❌ 未找到有效密码")
    print(f"📊 性能：{speed:.2f} 密码/秒 (总耗时：{elapsed_time:.2f}秒)")
    print(f"📈 共尝试了 {len(passwords)} 个密码")
    
    return None


def crack_pdf_password(input_file, dictionary_folder):
    """
    最终性能版密码破解：移除所有不必要的开销
    """
    start_time = time.time()
    
    # 收集所有密码（最简洁的方式）
    all_passwords = []
    for root, _, files in os.walk(dictionary_folder):
        for file in files:
            if file.endswith('.txt'):
                with open(os.path.join(root, file), 'r', encoding='utf-8', errors='ignore') as f:
                    all_passwords.extend(p.strip() for p in f if p.strip())
    
    if not all_passwords:
        print("字典中没有找到有效密码")
        return None
    
    print(f"总共找到 {len(all_passwords)} 个密码")
    
    # 极简优先级排序：仅按长度排序
    sorted_passwords = sorted(all_passwords, key=len)
    
    # 直接顺序尝试（最简洁最高效）
    tried_count = 0
    last_progress_time = start_time
    
    try:
        for password in sorted_passwords:
            try:
                with pikepdf.open(input_file, password=password) as pdf:
                    elapsed_time = time.time() - start_time
                    speed = (tried_count + 1) / elapsed_time
                    print(f"\n✅ 找到密码：{password}")
                    print(f"📊 性能：{speed:.2f} 密码/秒 (耗时：{elapsed_time:.2f}秒)")
                    print(f"📈 尝试了 {tried_count + 1} 个密码")
                    return password
            except (pikepdf.PasswordError, pikepdf.PdfError):
                tried_count += 1
                
                # 每1秒或每100个密码输出一次进度
                current_time = time.time()
                if current_time - last_progress_time >= 1.0 or tried_count % 100 == 0:
                    elapsed_time = current_time - start_time
                    speed = tried_count / elapsed_time if elapsed_time > 0 else 0
                    progress_pct = (tried_count / len(sorted_passwords) * 100) if len(sorted_passwords) > 0 else 0
                    print(f"⏳ 进度: {tried_count}/{len(sorted_passwords)} ({progress_pct:.1f}%), 速度: {speed:.2f} 密码/秒", end='\r')
                    last_progress_time = current_time
                
                continue
        
        # 如果循环正常结束（没找到密码）
        elapsed_time = time.time() - start_time
        speed = len(sorted_passwords) / elapsed_time if elapsed_time > 0 else 0
        print(f"\n❌ 未找到有效密码")
        print(f"📊 性能：{speed:.2f} 密码/秒 (总耗时：{elapsed_time:.2f}秒)")
        print(f"📈 共尝试了 {len(sorted_passwords)} 个密码")
        return None
        
    except KeyboardInterrupt:
        elapsed_time = time.time() - start_time
        speed = tried_count / elapsed_time if elapsed_time > 0 else 0
        print(f"\n\n⚠️ 用户中断（Ctrl+C）")
        print(f"📊 已尝试: {tried_count} 个密码")
        print(f"📊 速度: {speed:.2f} 密码/秒 (耗时: {elapsed_time:.2f}秒)")
        if len(sorted_passwords) > 0:
            progress_pct = (tried_count / len(sorted_passwords) * 100)
            print(f"📉 进度: {tried_count}/{len(sorted_passwords)} ({progress_pct:.1f}%)")
        # 抛出异常，让上层函数知道是用户中断
        raise KeyboardInterrupt("用户中断破解过程")

def remove_pdf_password_optimized(input_file, output_file, dictionary_folder, password=None, num_processes=8, batch_size=50):
    """
    高性能PDF密码移除（优化版）
    
    参数:
        input_file: 输入PDF文件路径
        output_file: 输出PDF文件路径
        dictionary_folder: 密码字典文件夹路径
        password: 已知密码（可选）
        num_processes: 进程数
        batch_size: 批次大小
    """
    # 首先尝试使用传入的密码
    if password:
        try:
            with pikepdf.open(input_file, password=password) as pdf:
                pdf.save(output_file)
                print(f"✅ 使用提供的密码解密成功")
                return
        except (pikepdf.PasswordError, pikepdf.PdfError):
            print("❌ 提供的密码不正确，开始字典破解...")
    
    # 尝试空密码
    try:
        with pikepdf.open(input_file, password='') as pdf:
            pdf.save(output_file)
            print(f"✅ 使用空密码解密成功")
            return
    except (pikepdf.PasswordError, pikepdf.PdfError):
        pass
    
    # 使用优化版破解
    try:
        found_password = crack_pdf_password_optimized(input_file, dictionary_folder, num_processes, batch_size)
    except KeyboardInterrupt:
        # 如果是在破解过程中被中断，crack_pdf_password_optimized 已经显示了性能数据
        # 这里直接退出，不抛出异常
        return
    
    if found_password:
        try:
            with pikepdf.open(input_file, password=found_password) as pdf:
                pdf.save(output_file)
            print(f"✅ 使用找到的密码解密成功：{output_file}")
        except Exception as e:
            print(f"❌ 使用找到的密码解密失败: {e}")
            raise
    else:
        # crack_pdf_password_optimized 已经打印了"未找到有效密码"和性能数据
        # 这里直接返回，不抛出异常，避免显示 Traceback
        return


def remove_pdf_password(input_file, output_file, dictionary_folder, password=None, num_processes=8, batch_size=50, use_optimized=True):
    """
    PDF密码移除（支持优化版本和标准版本）
    """
    # 如果启用优化版本，使用优化版本
    if use_optimized:
        return remove_pdf_password_optimized(input_file, output_file, dictionary_folder, password, num_processes, batch_size)
    
    # 否则使用标准版本
    # 首先尝试使用传入的密码
    if password:
        try:
            with pikepdf.open(input_file, password=password) as pdf:
                pdf.save(output_file)
                print(f"✅ 使用提供的密码解密成功")
                return
        except (pikepdf.PasswordError, pikepdf.PdfError):
            print("❌ 提供的密码不正确")
    
    # 尝试空密码
    try:
        with pikepdf.open(input_file, password='') as pdf:
            pdf.save(output_file)
            print(f"✅ 使用空密码解密成功")
            return
    except (pikepdf.PasswordError, pikepdf.PdfError):
        print("❌ 空密码解密失败")
    
    # 使用标准破解
    try:
        found_password = crack_pdf_password(input_file, dictionary_folder)
    except KeyboardInterrupt:
        # 如果是在破解过程中被中断，crack_pdf_password 已经显示了性能数据
        # 这里直接退出，不抛出异常
        return
    
    if found_password:
        with pikepdf.open(input_file, password=found_password) as pdf:
            pdf.save(output_file)
        print(f"✅ 使用找到的密码解密成功")
        print(f"✅ 解密成功：{output_file}")
    else:
        # crack_pdf_password 已经打印了"未找到有效密码"和性能数据
        # 这里直接返回，不抛出异常，避免显示 Traceback
        return




class SecurityRevision:
    """表示标准安全处理程序版本
    以及对应的 /O 和 /U 条目的密钥长度

    在版本5中，/O 和 /U 条目扩展到 48 字节，
    包含三个逻辑部分：32 字节验证哈希、
    8 字节验证盐和 8 字节密钥盐。"""

    revisions = {
        2: 32,  # RC4基础加密
        3: 32,  # RC4扩展加密
        4: 32,  # RC4或AES128加密
        5: 48,  # AES_R5_256加密
        6: 48,  # AES_256加密
    }

    @classmethod
    def get_key_length(cls, revision):
        """
        获取指定版本的密钥长度，
        如果未指定版本，默认返回 48。
        """
        return cls.revisions.get(revision, 48)


def extract_pdf_hash(pdf_file):
    """
    提取PDF文件的hash值（John the Ripper / Hashcat 格式）
    
    参数:
        pdf_file: PDF文件路径
        
    返回:
        tuple: (hash字符串, 加密信息字典) 或 None
        hash字符串格式为 $pdf$...
        加密信息字典包含: algorithm, revision, length, hashcat_mode
    """
    if not PYHANKO_AVAILABLE:
        print("❌ pyhanko 库不可用，无法提取 hash")
        print("   安装命令: pip install pyhanko")
        return None
    
    try:
        with open(pdf_file, "rb") as doc:
            pdf = PdfFileReader(doc, strict=False)
            encrypt_dict = pdf.encrypt_dict
            
            if not encrypt_dict:
                print("❌ PDF文件未加密，无法提取 hash")
                return None
            
            algorithm = encrypt_dict.get("/V")
            length = encrypt_dict.get("/Length", 40)
            permissions = encrypt_dict["/P"]
            revision = encrypt_dict["/R"]
            document_id = pdf.document_id[0]
            encrypt_metadata = str(int(pdf.security_handler.encrypt_metadata))
            
            # 提取密码相关数据
            passwords = []
            keys = ("udata", "odata", "oeseed", "ueseed")
            max_key_length = SecurityRevision.get_key_length(revision)
            
            for key in keys:
                if data := getattr(pdf.security_handler, key):
                    data = data[:max_key_length]
                    passwords.extend([str(len(data)), data.hex()])
            
            # 构建 hash 字符串
            fields = [
                f"$pdf${algorithm}",
                revision,
                length,
                permissions,
                encrypt_metadata,
                len(document_id),
                document_id.hex(),
                "*".join(passwords),
            ]
            
            hash_string = "*".join(map(str, fields))
            
            # 根据算法版本确定hashcat模式
            # -m 10500: PDF 1.4-1.6 (Acrobat 5-8), Revision 2-4, MD5
            # -m 10600: PDF 1.7 Level 3 (Acrobat 9), Revision 5, SHA256
            # -m 10700: PDF 1.7 Level 8 (Acrobat 10-11), Revision 6, SHA256
            if revision <= 4:
                hashcat_mode = 10500
                pdf_version = "PDF 1.4-1.6 (Acrobat 5-8)"
            elif revision == 5:
                hashcat_mode = 10600
                pdf_version = "PDF 1.7 Level 3 (Acrobat 9)"
            elif revision == 6:
                hashcat_mode = 10700
                pdf_version = "PDF 1.7 Level 8 (Acrobat 10-11)"
            else:
                hashcat_mode = 10500  # 默认
                pdf_version = f"PDF (Revision {revision})"
            
            encrypt_info = {
                'algorithm': algorithm,
                'revision': revision,
                'length': length,
                'hashcat_mode': hashcat_mode,
                'pdf_version': pdf_version
            }
            
            return (hash_string, encrypt_info)
            
    except PdfReadError as e:
        print(f"❌ 读取PDF文件失败: {e}")
        return None
    except RuntimeError as e:
        print(f"❌ {e}")
        return None
    except Exception as e:
        print(f"❌ 提取 hash 时出错: {e}")
        return None


def print_hashcat_usage(hash_file, hashcat_mode, pdf_version):
    """
    打印详细的hashcat使用说明
    
    参数:
        hash_file: hash文件路径
        hashcat_mode: hashcat模式号
        pdf_version: PDF版本描述
    """
    print("\n" + "=" * 70)
    print("🔧 Hashcat 使用指南")
    print("=" * 70)
    print(f"\n📋 PDF信息：{pdf_version}")
    print(f"📋 Hashcat模式：-m {hashcat_mode}")
    print(f"📋 Hash文件：{hash_file}")
    
    print("\n" + "-" * 70)
    print("🎯 攻击模式 (-a 参数)")
    print("-" * 70)
    
    print("\n1️⃣  字典攻击（Straight）- 推荐新手使用")
    print(f"   hashcat -m {hashcat_mode} -a 0 {hash_file} wordlist.txt")
    print("   说明：使用字典文件中的密码逐个尝试")
    
    print("\n2️⃣  组合攻击（Combination）")
    print(f"   hashcat -m {hashcat_mode} -a 1 {hash_file} wordlist1.txt wordlist2.txt")
    print("   说明：将两个字典中的密码组合（wordlist1 + wordlist2）")
    
    print("\n3️⃣  暴力破解（Brute-force）")
    print(f"   hashcat -m {hashcat_mode} -a 3 {hash_file} ?a?a?a?a?a?a")
    print("   说明：尝试所有可能的字符组合")
    print("   掩码说明：")
    print("     ?l = 小写字母 (a-z)")
    print("     ?u = 大写字母 (A-Z)")
    print("     ?d = 数字 (0-9)")
    print("     ?s = 特殊字符 (!@#$%^&*)")
    print("     ?a = 所有字符 (?l?u?d?s)")
    print("   示例：?a?a?a?a 表示4位任意字符")
    
    print("\n4️⃣  字典+掩码（Hybrid Wordlist + Mask）")
    print(f"   hashcat -m {hashcat_mode} -a 6 {hash_file} wordlist.txt ?d?d?d")
    print("   说明：字典中的每个密码 + 掩码后缀（如：password123）")
    
    print("\n5️⃣  掩码+字典（Hybrid Mask + Wordlist）")
    print(f"   hashcat -m {hashcat_mode} -a 7 {hash_file} ?d?d?d wordlist.txt")
    print("   说明：掩码前缀 + 字典中的每个密码（如：123password）")
    
    print("\n" + "-" * 70)
    print("⚙️  常用参数")
    print("-" * 70)
    print("   -O, --optimized-kernel-enable : 启用优化内核（更快，但限制密码长度）")
    print("   -w 3                          : 工作负载（1=低，2=中，3=高，4=最高）")
    print("   --show                        : 显示已破解的密码")
    print("   --remove                      : 破解成功后从hash文件中移除")
    print("   -o output.txt                 : 将结果保存到文件")
    print("   --session session_name        : 保存会话，可随时恢复")
    
    print("\n" + "-" * 70)
    print("💡 实用示例")
    print("-" * 70)
    print(f"\n# 基础字典攻击")
    print(f"hashcat -m {hashcat_mode} -a 0 {hash_file} rockyou.txt")
    
    print(f"\n# 使用字典目录（自动遍历目录下所有字典文件）")
    print(f"hashcat -m {hashcat_mode} -a 0 {hash_file} /path/to/dictionaries/*.txt")
    print(f"# 或使用通配符匹配多种格式")
    print(f"hashcat -m {hashcat_mode} -a 0 {hash_file} /path/to/dictionaries/*")
    print(f"# 说明：hashcat会自动遍历目录下所有匹配的文件作为字典")
    
    print(f"\n# 字典攻击 + 显示进度")
    print(f"hashcat -m {hashcat_mode} -a 0 -w 3 {hash_file} rockyou.txt --show")
    
    print(f"\n# 暴力破解4-6位数字密码")
    print(f"hashcat -m {hashcat_mode} -a 3 {hash_file} ?d?d?d?d --increment")
    print(f"hashcat -m {hashcat_mode} -a 3 {hash_file} ?d?d?d?d?d?d --increment")
    
    print(f"\n# 字典 + 常见后缀（如：password123）")
    print(f"hashcat -m {hashcat_mode} -a 6 {hash_file} wordlist.txt ?d?d?d")
    
    print(f"\n# 保存会话，可随时恢复")
    print(f"hashcat -m {hashcat_mode} -a 0 {hash_file} wordlist.txt --session my_session")
    print(f"# 恢复会话：hashcat --session my_session --restore")
    
    print("\n" + "=" * 70)


def print_john_usage(hash_file, pdf_version):
    """
    打印详细的John the Ripper使用说明
    
    参数:
        hash_file: hash文件路径
        pdf_version: PDF版本描述
    """
    print("\n" + "=" * 70)
    print("🔧 John the Ripper 使用指南")
    print("=" * 70)
    print(f"\n📋 PDF信息：{pdf_version}")
    print(f"📋 Hash文件：{hash_file}")
    
    print("\n" + "-" * 70)
    print("🎯 基础用法")
    print("-" * 70)
    
    print("\n1️⃣  字典攻击（Wordlist Mode）")
    print(f"   john --wordlist=wordlist.txt --format=PDF {hash_file}")
    print("   或简写：")
    print(f"   john --wordlist=wordlist.txt {hash_file}")
    print("   说明：使用字典文件中的密码逐个尝试")
    
    print("\n2️⃣  暴力破解（Incremental Mode）")
    print(f"   john --incremental --format=PDF {hash_file}")
    print("   说明：尝试所有可能的字符组合（非常耗时）")
    
    print("\n3️⃣  单破解模式（Single Crack Mode）")
    print(f"   john --single --format=PDF {hash_file}")
    print("   说明：基于用户名/文件名生成密码变体")
    
    print("\n" + "-" * 70)
    print("📝 使用规则（Rules）")
    print("-" * 70)
    print("   规则可以对字典中的密码进行变换，生成更多变体")
    
    print("\n1️⃣  使用内置规则")
    print(f"   john --wordlist=wordlist.txt --rules --format=PDF {hash_file}")
    print("   说明：使用默认规则集（推荐）")
    
    print("\n2️⃣  使用自定义规则文件")
    print(f"   john --wordlist=wordlist.txt --rules=myrules.conf --format=PDF {hash_file}")
    print("   说明：使用自定义规则文件")
    
    print("\n3️⃣  使用特定规则集")
    print(f"   john --wordlist=wordlist.txt --rules=Best64 --format=PDF {hash_file}")
    print("   说明：使用Best64规则集（常见规则集：Best64, RockYou-30000, T0XlCv1等）")
    
    print("\n4️⃣  查看可用规则集")
    print("   john --list=rule-sets")
    print("   说明：列出所有可用的规则集")
    
    print("\n" + "-" * 70)
    print("⚙️  常用参数")
    print("-" * 70)
    print("   --show                        : 显示已破解的密码")
    print("   --show=left                   : 显示未破解的hash")
    print("   --show=formats                : 显示所有支持的格式")
    print("   --format=PDF                 : 指定hash格式（PDF会自动识别）")
    print("   --fork=N                     : 使用N个进程并行破解（默认：CPU核心数）")
    print("   --session=session_name       : 保存会话，可随时恢复")
    print("   --restore=session_name       : 恢复之前的会话")
    print("   --status                     : 显示破解进度")
    print("   --status=STATUS              : 每STATUS秒更新一次进度")
    print("   --stdout                     : 将破解的密码输出到标准输出")
    print("   --pot=potfile                : 指定pot文件路径（存储已破解的密码）")
    print("   --remove                     : 破解成功后从hash文件中移除")
    print("   --max-len=N                  : 限制密码最大长度为N")
    print("   --min-len=N                  : 限制密码最小长度为N")
    
    print("\n" + "-" * 70)
    print("💡 实用示例")
    print("-" * 70)
    
    print(f"\n# 基础字典攻击")
    print(f"john --wordlist=rockyou.txt {hash_file}")
    
    print(f"\n# 字典攻击 + 规则（推荐）")
    print(f"john --wordlist=rockyou.txt --rules {hash_file}")
    
    print(f"\n# 使用特定规则集")
    print(f"john --wordlist=rockyou.txt --rules=Best64 {hash_file}")
    
    print(f"\n# 显示破解进度（每10秒更新）")
    print(f"john --wordlist=rockyou.txt --rules --status=10 {hash_file}")
    
    print(f"\n# 使用多个进程加速（8进程）")
    print(f"john --wordlist=rockyou.txt --rules --fork=8 {hash_file}")
    
    print(f"\n# 保存会话，可随时恢复")
    print(f"john --wordlist=rockyou.txt --rules --session=my_session {hash_file}")
    print(f"# 恢复会话：john --restore=my_session")
    
    print(f"\n# 显示已破解的密码")
    print(f"john --show {hash_file}")
    
    print(f"\n# 限制密码长度（4-8位）")
    print(f"john --wordlist=wordlist.txt --rules --min-len=4 --max-len=8 {hash_file}")
    
    print(f"\n# 暴力破解（仅数字，4-6位）")
    print(f"john --incremental=Digits --min-len=4 --max-len=6 {hash_file}")
    
    print(f"\n# 组合使用：字典 + 规则 + 多进程 + 进度显示")
    print(f"john --wordlist=rockyou.txt --rules --fork=8 --status=5 {hash_file}")
    
    print("\n" + "-" * 70)
    print("📚 规则文件位置")
    print("-" * 70)
    print("   Linux:   /usr/share/john/rules/")
    print("   macOS:   /opt/homebrew/share/john/rules/ 或 /usr/local/share/john/rules/")
    print("   Windows: C:\\Program Files\\John the Ripper\\run\\rules\\")
    print("\n   常用规则集：")
    print("     - Best64.rule      : 64条最佳规则")
    print("     - T0XlCv1.rule      : 复杂规则集")
    print("     - RockYou-30000.rule : 基于RockYou字典的规则")
    print("     - leetspeak.rule   : 1337转换规则")
    
    print("\n" + "-" * 70)
    print("🔍 查看和调试")
    print("-" * 70)
    print("   # 测试规则效果（不实际破解）")
    print("   john --wordlist=wordlist.txt --rules --stdout | head -20")
    print("   说明：查看规则生成的密码变体")
    
    print("\n   # 查看支持的格式")
    print("   john --list=formats | grep -i pdf")
    
    print("\n   # 查看规则集列表")
    print("   john --list=rule-sets")
    
    print("\n" + "=" * 70)


def set_encrypt_pdf(input_file, output_file, password):
    """
    为PDF文件添加密码保护
    """
    with pikepdf.open(input_file) as pdf:
        pdf.save(output_file, encryption=pikepdf.Encryption(owner=password, user=password))
    print(f"✅ 加密成功：{output_file}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='PDF文件加密与解密工具')
    parser.add_argument('action', choices=['encrypt', 'decrypt', 'hash'], help='操作类型')
    parser.add_argument('-i', '--input', required=True, help='输入PDF文件路径')
    parser.add_argument('-o', '--output', help='输出文件路径（encrypt/decrypt/hash时必需）')
    parser.add_argument('-p', '--password', help='密码')
    parser.add_argument('-d', '--dictionary', default='./password_brute_dictionary', help='密码字典文件夹路径')
    parser.add_argument('-t', '--threads', type=int, default=8, help='进程数（默认8，仅优化版本有效）')
    parser.add_argument('-b', '--batch-size', type=int, default=50, help='批次大小（默认50，仅优化版本有效）')
    parser.add_argument('--no-optimized', action='store_true', help='禁用优化版本，使用标准版本')
    
    args = parser.parse_args()
    
    if args.action == 'encrypt':
        if not args.output:
            print("❌ 加密需要指定输出文件路径 (-o)")
            exit(1)
        if not args.password:
            print("❌ 加密需要密码")
            exit(1)
        print(f"🔒 加密：{args.input} -> {args.output}")
        set_encrypt_pdf(args.input, args.output, args.password)
    
    elif args.action == 'decrypt':
        if not args.output:
            print("❌ 解密需要指定输出文件路径 (-o)")
            exit(1)
        print(f"🔓 解密：{args.input} -> {args.output}")
        use_optimized = not args.no_optimized
        
        if use_optimized:
            print(f"🚀 使用优化版本（{args.threads}进程，批次大小{args.batch_size}）")
        else:
            print("📝 使用标准版本")
        remove_pdf_password(args.input, args.output, args.dictionary, args.password, 
                          args.threads, args.batch_size, use_optimized)
    
    elif args.action == 'hash':
        if not args.output:
            print("❌ hash操作需要指定输出文件路径 (-o)")
            exit(1)
        print(f"🔍 提取PDF hash值：{args.input}")
        result = extract_pdf_hash(args.input)
        if result:
            pdf_hash, encrypt_info = result
            hashcat_mode = encrypt_info['hashcat_mode']
            pdf_version = encrypt_info['pdf_version']
            
            # 保存hash到文件
            try:
                with open(args.output, 'w') as f:
                    f.write(pdf_hash + '\n')
                print(f"✅ Hash已保存到文件：{args.output}")
                print_hashcat_usage(args.output, hashcat_mode, pdf_version)
                print_john_usage(args.output, pdf_version)
            except Exception as e:
                print(f"❌ 保存hash到文件失败: {e}")