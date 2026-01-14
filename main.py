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
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
import re

class PDFPasswordCracker:
    def __init__(self, input_file):
        self.lock = threading.Lock()
        self.found_password = None
        self.input_file = input_file
        self.start_time = time.time()
        
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

def crack_pdf_password_high_performance(input_file, dictionary_folder, max_workers=8):
    """
    高性能密码破解：使用多线程但保持单密码尝试的高效率
    """
    cracker = PDFPasswordCracker(input_file)
    
    # 收集所有密码
    all_passwords = []
    for root, _, files in os.walk(dictionary_folder):
        for file in files:
            dictionary_file = os.path.join(root, file)
            with open(dictionary_file, 'r', encoding='utf-8', errors='ignore') as dict_file:
                passwords = [p.strip() for p in dict_file.readlines() if p.strip()]
                all_passwords.extend(passwords)
    
    if not all_passwords:
        print("字典中没有找到有效密码")
        return None
    
    print(f"总共找到 {len(all_passwords)} 个密码，使用 {max_workers} 个线程进行破解...")
    
    # 应用密码优先级排序
    prioritized_passwords = prioritize_passwords(all_passwords)
    
    # 使用线程池并行尝试密码（单密码模式）
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有密码尝试任务（按优先级顺序）
        future_to_password = {
            executor.submit(cracker.try_password, password): password 
            for password in prioritized_passwords
        }
        
        # 使用进度条显示进度
        with tqdm(total=len(prioritized_passwords), desc='正在尝试密码') as pbar:
            for future in as_completed(future_to_password):
                result = future.result()
                if result:
                    # 找到密码，取消其他任务
                    executor.shutdown(wait=False)
                    elapsed_time = time.time() - cracker.start_time
                    print(f"\\n找到密码：{result} (耗时: {elapsed_time:.2f}秒)")
                    print(f"密码在优先级列表中的位置：{prioritized_passwords.index(result) + 1}/{len(prioritized_passwords)}")
                    return result
                pbar.update(1)
    
    elapsed_time = time.time() - cracker.start_time
    print(f"密码破解完成，未找到有效密码 (总耗时: {elapsed_time:.2f}秒)")
    return None

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

if __name__ == '__main__':
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description='PDF文件加密与解密工具')
    parser.add_argument('action', choices=['encrypt', 'decrypt'], help='操作类型：encrypt(加密) 或 decrypt(解密)')
    parser.add_argument('-i', '--input', required=True, help='输入PDF文件路径')
    parser.add_argument('-o', '--output', required=True, help='输出PDF文件路径')
    parser.add_argument('-p', '--password', help='密码（加密时必需，解密时可选）')
    parser.add_argument('-d', '--dictionary', default='./password_brute_dictionary', help='密码字典文件夹路径（解密时使用）')
    parser.add_argument('-t', '--threads', type=int, default=8, help='解密时使用的线程数（默认8个，macOS推荐）')
    
    args = parser.parse_args()
    
    if args.action == 'encrypt':
        if not args.password:
            print("错误：加密操作需要指定密码，请使用 -p 参数")
            exit(1)
        print(f"正在加密文件：{args.input} -> {args.output}")
        set_encrypt_pdf(args.input, args.output, args.password)
    
    elif args.action == 'decrypt':
        print(f"正在解密文件：{args.input} -> {args.output}")
        remove_pdf_password_high_performance(args.input, args.output, args.dictionary, args.password, args.threads)
