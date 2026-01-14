'''
Description: PDF 文件的加密与去密
Version: 2.6 (最终性能版)
Author: Glenn
Email: chenluda01@outlook.com
Date: 2023-05-15 14:07:20
Copyright (c) 2023 by Kust-BME, All Rights Reserved. 
'''
import pikepdf
import os
import argparse
import time

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
    for password in sorted_passwords:
        try:
            with pikepdf.open(input_file, password=password) as pdf:
                elapsed_time = time.time() - start_time
                speed = (tried_count + 1) / elapsed_time
                print(f"✅ 找到密码：{password}")
                print(f"📊 性能：{speed:.2f} 密码/秒 (耗时：{elapsed_time:.2f}秒)")
                return password
        except (pikepdf.PasswordError, pikepdf.PdfError):
            tried_count += 1
            continue
    
    elapsed_time = time.time() - start_time
    speed = len(sorted_passwords) / elapsed_time
    print(f"❌ 未找到有效密码")
    print(f"📊 性能：{speed:.2f} 密码/秒 (总耗时：{elapsed_time:.2f}秒)")
    return None

def remove_pdf_password(input_file, output_file, dictionary_folder, password=None):
    """
    最终性能版PDF密码移除
    """
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
    
    # 使用最终性能破解
    found_password = crack_pdf_password(input_file, dictionary_folder)
    
    if found_password:
        with pikepdf.open(input_file, password=found_password) as pdf:
            pdf.save(output_file)
        print(f"✅ 使用找到的密码解密成功")
    else:
        print("❌ 未找到有效密码")
        raise Exception("未找到有效密码")
    
    print(f"✅ 解密成功：{output_file}")

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
    
    args = parser.parse_args()
    
    if args.action == 'encrypt':
        if not args.password:
            print("❌ 加密需要密码")
            exit(1)
        print(f"🔒 加密：{args.input} -> {args.output}")
        set_encrypt_pdf(args.input, args.output, args.password)
    
    elif args.action == 'decrypt':
        print(f"🔓 解密：{args.input} -> {args.output}")
        remove_pdf_password(args.input, args.output, args.dictionary, args.password)
