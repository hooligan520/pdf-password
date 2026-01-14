'''
Description: PDF 文件的加密与去密
Version: 2.3
Author: Glenn
Email: chenluda01@outlook.com
Date: 2023-05-15 14:07:20
Copyright (c) 2023 by Kust-BME, All Rights Reserved. 
'''
import pikepdf
import os
import argparse
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import threading
import time
import re
import mmap
import hashlib
from functools import lru_cache

class PDFPasswordCracker:
    def __init__(self, input_file):
        self.lock = threading.Lock()
        self.found_password = None
        self.input_file = input_file
        self.start_time = time.time()
        # 预加载PDF文件内容到内存
        self.pdf_content = self._load_pdf_to_memory()
        
    def _load_pdf_to_memory(self):
        """将PDF文件内容预加载到内存，避免重复文件I/O"""
        with open(self.input_file, 'rb') as f:
            return f.read()
    
    def try_password(self, password):
        """单密码尝试，避免重复文件打开"""
        if self.found_password:
            return None
            
        try:
            with pikepdf.open(self.input_file, password=password.strip()) as pdf:
                with self.lock:
                    if not self.found_password:
                        self.found_password = password.strip()
                        return password.strip()
        except (pikepdf.PasswordError, pikepdf.PdfError):
            pass
        return None
    
    def try_password_batch(self, passwords_batch):
        """批量密码尝试，显著减少文件I/O操作"""
        if self.found_password:
            return None
            
        # 为每个批次创建唯一的临时文件
        batch_hash = hashlib.md5(str(passwords_batch).encode()).hexdigest()[:8]
        temp_file = f"/tmp/temp_pdf_{batch_hash}.pdf"
        
        # 写入临时文件
        with open(temp_file, 'wb') as f:
            f.write(self.pdf_content)
        
        try:
            for password in passwords_batch:
                if self.found_password:
                    break
                    
                try:
                    with pikepdf.open(temp_file, password=password.strip()) as pdf:
                        with self.lock:
                            if not self.found_password:
                                self.found_password = password.strip()
                                return password.strip()
                except (pikepdf.PasswordError, pikepdf.PdfError):
                    continue
        finally:
            # 确保临时文件被清理
            if os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except:
                    pass  # 忽略清理错误
        
        return None

def prioritize_passwords(passwords):
    """
    智能密码优先级排序：
    1. 短密码（1-6位）优先
    2. 纯数字密码优先
    3. 常见弱密码优先
    4. 按长度从小到大排序
    """
    # 常见弱密码列表（高优先级）
    common_passwords = [
        '123456', 'password', '12345678', '1234', '12345', '123456789',
        '123', '000000', '111111', 'admin', 'qwerty', 'abc123',
        '123123', '1234567', '1234567890', 'password1', '123qwe'
    ]
    
    def get_password_priority(password):
        # 优先级评分：分数越低优先级越高
        priority = 0
        
        # 1. 长度优先级：越短优先级越高
        length = len(password)
        if length <= 3:
            priority += 0  # 最高优先级
        elif length <= 6:
            priority += 100
        elif length <= 8:
            priority += 200
        else:
            priority += 300
        
        # 2. 常见密码优先级
        if password.lower() in common_passwords:
            priority -= 50  # 显著提高优先级
        
        # 3. 纯数字密码优先级
        if password.isdigit():
            priority -= 20  # 提高优先级
        
        # 4. 简单模式优先级（如重复数字、连续数字）
        if re.match(r'^(\\d)\\1+$', password):  # 重复数字
            priority -= 30
        elif re.match(r'^\\d+$', password):  # 连续数字
            if len(password) <= 6:
                priority -= 15
        
        return priority
    
    # 按优先级排序
    sorted_passwords = sorted(passwords, key=get_password_priority)
    
    # 打印排序统计信息
    total_passwords = len(sorted_passwords)
    short_passwords = len([p for p in sorted_passwords if len(p) <= 6])
    numeric_passwords = len([p for p in sorted_passwords if p.isdigit()])
    common_count = len([p for p in sorted_passwords if p.lower() in common_passwords])
    
    print(f"密码优先级排序完成：")
    print(f"  - 总密码数：{total_passwords}")
    print(f"  - 短密码（≤6位）：{short_passwords}")
    print(f"  - 纯数字密码：{numeric_passwords}")
    print(f"  - 常见弱密码：{common_count}")
    print(f"  - 前10个高优先级密码：{sorted_passwords[:10]}")
    
    return sorted_passwords

def crack_pdf_password_simple(input_file, dictionary_folder, max_workers=1):
    """
    简单高效的密码破解：单线程+优先级排序，避免不必要的复杂性
    """
    print(f"使用简单高效模式破解密码...")
    start_time = time.time()
    
    # 收集所有密码
    all_passwords = []
    for root, _, files in os.walk(dictionary_folder):
        for file in files:
            if file.endswith('.txt'):
                dictionary_file = os.path.join(root, file)
                with open(dictionary_file, 'r', encoding='utf-8', errors='ignore') as dict_file:
                    passwords = [p.strip() for p in dict_file.readlines() if p.strip()]
                    all_passwords.extend(passwords)
    
    if not all_passwords:
        print("字典中没有找到有效密码")
        return None
    
    print(f"总共找到 {len(all_passwords)} 个密码")
    
    # 应用密码优先级排序
    prioritized_passwords = prioritize_passwords(all_passwords)
    
    # 单线程顺序尝试（最简单最高效）
    tried_count = 0
    for password in tqdm(prioritized_passwords, desc='正在尝试密码'):
        try:
            with pikepdf.open(input_file, password=password) as pdf:
                elapsed_time = time.time() - start_time
                print(f"\n✅ 找到密码：{password}")
                print(f"📊 性能统计：")
                print(f"   - 耗时：{elapsed_time:.2f}秒")
                print(f"   - 已尝试：{tried_count + 1}/{len(prioritized_passwords)} 个密码")
                print(f"   - 速度：{(tried_count + 1) / elapsed_time:.2f} 密码/秒")
                print(f"   - 密码优先级位置：{prioritized_passwords.index(password) + 1}")
                return password
        except (pikepdf.PasswordError, pikepdf.PdfError):
            tried_count += 1
            continue
    
    elapsed_time = time.time() - start_time
    print(f"\n❌ 未找到有效密码")
    print(f"📊 性能统计：")
    print(f"   - 总耗时：{elapsed_time:.2f}秒")
    print(f"   - 总尝试：{len(prioritized_passwords)} 个密码")
    print(f"   - 平均速度：{len(prioritized_passwords) / elapsed_time:.2f} 密码/秒")
    return None

def crack_pdf_password_optimized(input_file, dictionary_folder, max_workers=4):
    """
    优化版密码破解：轻量级多线程，避免过度工程化
    """
    print(f"使用优化模式破解密码（{max_workers}线程）...")
    start_time = time.time()
    found_password = None
    lock = threading.Lock()
    
    # 收集所有密码
    all_passwords = []
    for root, _, files in os.walk(dictionary_folder):
        for file in files:
            if file.endswith('.txt'):
                dictionary_file = os.path.join(root, file)
                with open(dictionary_file, 'r', encoding='utf-8', errors='ignore') as dict_file:
                    passwords = [p.strip() for p in dict_file.readlines() if p.strip()]
                    all_passwords.extend(passwords)
    
    if not all_passwords:
        print("字典中没有找到有效密码")
        return None
    
    print(f"总共找到 {len(all_passwords)} 个密码")
    
    # 应用密码优先级排序
    prioritized_passwords = prioritize_passwords(all_passwords)
    
    def try_password_thread(password):
        nonlocal found_password
        if found_password:
            return None
            
        try:
            with pikepdf.open(input_file, password=password) as pdf:
                with lock:
                    if not found_password:
                        found_password = password
                        return password
        except (pikepdf.PasswordError, pikepdf.PdfError):
            return None
        return None
    
    # 简单的多线程实现
    threads = []
    password_index = 0
    
    with tqdm(total=len(prioritized_passwords), desc='正在尝试密码') as pbar:
        while password_index < len(prioritized_passwords) and not found_password:
            # 创建线程（不超过最大线程数）
            active_threads = [t for t in threads if t.is_alive()]
            if len(active_threads) < max_workers:
                password = prioritized_passwords[password_index]
                thread = threading.Thread(target=try_password_thread, args=(password,))
                thread.start()
                threads.append(thread)
                password_index += 1
                pbar.update(1)
            else:
                time.sleep(0.01)  # 短暂等待
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
    
    elapsed_time = time.time() - start_time
    if found_password:
        print(f"\n✅ 找到密码：{found_password}")
        print(f"📊 性能统计：")
        print(f"   - 耗时：{elapsed_time:.2f}秒")
        print(f"   - 速度：{password_index / elapsed_time:.2f} 密码/秒")
    else:
        print(f"\n❌ 未找到有效密码")
        print(f"📊 性能统计：")
        print(f"   - 总耗时：{elapsed_time:.2f}秒")
        print(f"   - 总尝试：{len(prioritized_passwords)} 个密码")
        print(f"   - 平均速度：{len(prioritized_passwords) / elapsed_time:.2f} 密码/秒")
    
    return found_password

def remove_pdf_password_high_performance(input_file, output_file, dictionary_folder, password=None, max_workers=8):
    """
    高性能PDF密码移除函数
    """
    try:
        # 首先尝试使用传入的密码
        if password:
            print(f"尝试使用提供的密码进行解密...")
            start_time = time.time()
            try:
                with pikepdf.open(input_file, password=password) as pdf:
                    pdf.save(output_file)
                    elapsed_time = time.time() - start_time
                    print(f"使用提供的密码解密成功 (耗时: {elapsed_time:.2f}秒)")
                    return
            except (pikepdf.PasswordError, pikepdf.PdfError):
                print("提供的密码不正确")
        
        # 尝试空密码
        print("尝试使用空密码进行解密...")
        start_time = time.time()
        try:
            with pikepdf.open(input_file, password='') as pdf:
                pdf.save(output_file)
                elapsed_time = time.time() - start_time
                print(f"使用空密码解密成功 (耗时: {elapsed_time:.2f}秒)")
                return
        except (pikepdf.PasswordError, pikepdf.PdfError):
            print("空密码解密失败")
        
        # 使用高性能字典破解（带优先级排序）
        print("开始高性能字典破解（带优先级排序）...")
        found_password = crack_pdf_password_high_performance(input_file, dictionary_folder, max_workers)
        
        if found_password:
            try:
                with pikepdf.open(input_file, password=found_password) as pdf:
                    pdf.save(output_file)
                    print(f"使用字典找到的密码 '{found_password}' 解密成功")
            except (pikepdf.PasswordError, pikepdf.PdfError):
                print(f"字典密码 '{found_password}' 解密失败")
                raise Exception("File has not been decrypted")
        else:
            print("未找到有效密码")
            raise Exception("No valid password found")
            
        print(f"解密成功，已生成新文件：{output_file}")

    except Exception as e:
        print(f"发生错误：{e}")
        raise

def remove_pdf_password_ultra_performance(input_file, output_file, dictionary_folder, password=None, max_workers=8, batch_size=100):
    """
    超高性能PDF密码移除函数
    """
    try:
        # 首先尝试使用传入的密码
        if password:
            print(f"尝试使用提供的密码进行解密...")
            start_time = time.time()
            try:
                with pikepdf.open(input_file, password=password) as pdf:
                    pdf.save(output_file)
                    elapsed_time = time.time() - start_time
                    print(f"使用提供的密码解密成功 (耗时: {elapsed_time:.2f}秒)")
                    return
            except (pikepdf.PasswordError, pikepdf.PdfError):
                print("提供的密码不正确")
        
        # 尝试空密码
        print("尝试使用空密码进行解密...")
        start_time = time.time()
        try:
            with pikepdf.open(input_file, password='') as pdf:
                pdf.save(output_file)
                elapsed_time = time.time() - start_time
                print(f"使用空密码解密成功 (耗时: {elapsed_time:.2f}秒)")
                return
        except (pikepdf.PasswordError, pikepdf.PdfError):
            print("空密码解密失败")
        
        # 使用超高性能破解（进程池+批量验证）
        print("开始超高性能密码破解（进程池+批量验证）...")
        found_password = crack_pdf_password_ultra_performance(input_file, dictionary_folder, max_workers, batch_size)
        
        if found_password:
            try:
                with pikepdf.open(input_file, password=found_password) as pdf:
                    pdf.save(output_file)
                    print(f"使用字典找到的密码 '{found_password}' 解密成功")
            except (pikepdf.PasswordError, pikepdf.PdfError):
                print(f"字典密码 '{found_password}' 解密失败")
                raise Exception("File has not been decrypted")
        else:
            print("未找到有效密码")
            raise Exception("No valid password found")
            
        print(f"解密成功，已生成新文件：{output_file}")

    except Exception as e:
        print(f"发生错误：{e}")
        raise

def set_encrypt_pdf(input_file, output_file, password):
    """
    为PDF文件添加密码保护
    """
    try:
        with pikepdf.open(input_file) as pdf:
            # 使用pikepdf的加密功能
            pdf.save(output_file, encryption=pikepdf.Encryption(owner=password, user=password))
        print(f"成功加密 PDF 文件，已生成新文件：{output_file}")

    except Exception as e:
        print(f"发生错误：{e}")

def remove_pdf_password_optimized(input_file, output_file, dictionary_folder, password=None, max_workers=1, mode='simple'):
    """
    优化版PDF密码移除函数
    """
    try:
        # 首先尝试使用传入的密码
        if password:
            print(f"尝试使用提供的密码进行解密...")
            start_time = time.time()
            try:
                with pikepdf.open(input_file, password=password) as pdf:
                    pdf.save(output_file)
                    elapsed_time = time.time() - start_time
                    print(f"✅ 使用提供的密码解密成功 (耗时: {elapsed_time:.2f}秒)")
                    return
            except (pikepdf.PasswordError, pikepdf.PdfError):
                print("❌ 提供的密码不正确")
        
        # 尝试空密码
        print("尝试使用空密码进行解密...")
        start_time = time.time()
        try:
            with pikepdf.open(input_file, password='') as pdf:
                pdf.save(output_file)
                elapsed_time = time.time() - start_time
                print(f"✅ 使用空密码解密成功 (耗时: {elapsed_time:.2f}秒)")
                return
        except (pikepdf.PasswordError, pikepdf.PdfError):
            print("❌ 空密码解密失败")
        
        # 根据模式选择破解方法
        if mode == 'simple':
            print("🔹 使用简单高效模式（单线程+优先级排序）")
            found_password = crack_pdf_password_simple(input_file, dictionary_folder, max_workers)
        elif mode == 'optimized':
            print("🔸 使用优化模式（轻量级多线程）")
            found_password = crack_pdf_password_optimized(input_file, dictionary_folder, max_workers)
        else:
            print("🔹 默认使用简单高效模式")
            found_password = crack_pdf_password_simple(input_file, dictionary_folder, max_workers)
        
        if found_password:
            try:
                with pikepdf.open(input_file, password=found_password) as pdf:
                    pdf.save(output_file)
                    print(f"✅ 使用字典找到的密码 '{found_password}' 解密成功")
            except (pikepdf.PasswordError, pikepdf.PdfError):
                print(f"❌ 字典密码 '{found_password}' 解密失败")
                raise Exception("文件解密失败")
        else:
            print("❌ 未找到有效密码")
            raise Exception("未找到有效密码")
            
        print(f"✅ 解密成功，已生成新文件：{output_file}")

    except Exception as e:
        print(f"❌ 发生错误：{e}")
        raise

if __name__ == '__main__':
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description='PDF文件加密与解密工具')
    parser.add_argument('action', choices=['encrypt', 'decrypt'], help='操作类型：encrypt(加密) 或 decrypt(解密)')
    parser.add_argument('-i', '--input', required=True, help='输入PDF文件路径')
    parser.add_argument('-o', '--output', required=True, help='输出PDF文件路径')
    parser.add_argument('-p', '--password', help='密码（加密时必需，解密时可选）')
    parser.add_argument('-d', '--dictionary', default='./password_brute_dictionary', help='密码字典文件夹路径（解密时使用）')
    parser.add_argument('-t', '--threads', type=int, default=1, help='解密时使用的线程数（默认1个，简单模式推荐）')
    parser.add_argument('-m', '--mode', choices=['simple', 'optimized'], default='simple', help='破解模式：simple(简单高效) 或 optimized(优化多线程)')
    
    args = parser.parse_args()
    
    if args.action == 'encrypt':
        if not args.password:
            print("❌ 错误：加密操作需要指定密码，请使用 -p 参数")
            exit(1)
        print(f"🔒 正在加密文件：{args.input} -> {args.output}")
        set_encrypt_pdf(args.input, args.output, args.password)
    
    elif args.action == 'decrypt':
        print(f"🔓 正在解密文件：{args.input} -> {args.output}")
        remove_pdf_password_optimized(args.input, args.output, args.dictionary, args.password, args.threads, args.mode)
