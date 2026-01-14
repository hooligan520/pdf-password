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

def verify_password_in_memory(pdf_data, password):
    """
    在内存中验证PDF密码，避免磁盘I/O
    
    Args:
        pdf_data: PDF文件的二进制数据
        password: 要验证的密码
        
    Returns:
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
    
    Args:
        pdf_data: PDF文件的二进制数据
        password_batch: 密码批次（列表）
        
    Returns:
        str or None: 第一个成功的密码，如果没有则返回None
    """
    for password in password_batch:
        if verify_password_in_memory(pdf_data, password):
            return password
    return None


def verify_password_worker(args):
    """
    工作进程函数：验证一批密码
    
    Args:
        args: (pdf_data, password_batch) 元组
        
    Returns:
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
    
    Args:
        dictionary_folder: 字典文件夹路径
        
    Returns:
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
    
    Args:
        input_file: PDF文件路径
        dictionary_folder: 密码字典文件夹路径
        num_processes: 进程数（默认8）
        batch_size: 每个进程处理的密码批次大小（默认50）
        
    Returns:
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
    
    Args:
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
        print("❌ 未找到有效密码")
        raise Exception("未找到有效密码")


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
        print("❌ 未找到有效密码")
        raise Exception("未找到有效密码")

def set_encrypt_pdf(input_file, output_file, password):
    """
    为PDF文件添加密码保护
    """
    with pikepdf.open(input_file) as pdf:
        pdf.save(output_file, encryption=pikepdf.Encryption(owner=password, user=password))
    print(f"✅ 加密成功：{output_file}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='PDF文件加密与解密工具')
    parser.add_argument('action', choices=['encrypt', 'decrypt'], help='操作类型')
    parser.add_argument('-i', '--input', required=True, help='输入PDF文件路径')
    parser.add_argument('-o', '--output', required=True, help='输出PDF文件路径')
    parser.add_argument('-p', '--password', help='密码')
    parser.add_argument('-d', '--dictionary', default='./password_brute_dictionary', help='密码字典文件夹路径')
    parser.add_argument('-t', '--threads', type=int, default=8, help='进程数（默认8，仅优化版本有效）')
    parser.add_argument('-b', '--batch-size', type=int, default=50, help='批次大小（默认50，仅优化版本有效）')
    parser.add_argument('--no-optimized', action='store_true', help='禁用优化版本，使用标准版本')
    
    args = parser.parse_args()
    
    if args.action == 'encrypt':
        if not args.password:
            print("❌ 加密需要密码")
            exit(1)
        print(f"🔒 加密：{args.input} -> {args.output}")
        set_encrypt_pdf(args.input, args.output, args.password)
    
    elif args.action == 'decrypt':
        print(f"🔓 解密：{args.input} -> {args.output}")
        use_optimized = not args.no_optimized
        if use_optimized:
            print(f"🚀 使用优化版本（{args.threads}进程，批次大小{args.batch_size}）")
        else:
            print("📝 使用标准版本")
        remove_pdf_password(args.input, args.output, args.dictionary, args.password, 
                          args.threads, args.batch_size, use_optimized)
