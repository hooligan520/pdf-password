'''
Description: PDF 文件的加密与去密
Version: 1.0
Author: Glenn
Email: chenluda01@outlook.com
Date: 2023-05-15 14:07:20
Copyright (c) 2023 by Kust-BME, All Rights Reserved. 
'''
import PyPDF2
import os
import pikepdf
from tqdm import tqdm
import argparse

def crack_pdf_password(input_file, dictionary_folder):
    """
    使用字典破解PDF密码
    """
    # 遍历字典文件夹
    for root, _, files in os.walk(dictionary_folder):
        for file in files:
            # 获取子字典文件的路径
            dictionary_file = os.path.join(root, file)
            # 打开子字典文件
            with open(dictionary_file, 'r', encoding='utf-8') as dict_file:
                # 读取密码列表
                passwords = dict_file.readlines()
                
            # 尝试每个密码
            for password in tqdm(passwords, desc='正在尝试密码'):
                try:
                    # 使用密码尝试打开 PDF
                    with pikepdf.open(input_file, password=password.strip()) as pdf:
                        print(f"\n找到密码：{password.strip()}")
                        return password
                except pikepdf.PasswordError as e:
                    pass

def remove_pdf_password(input_file, output_file, dictionary_folder, password=None):
    """
    移除 PDF 文件的密码保护
    """
    try:
        with open(input_file, 'rb') as file:
            # 创建PDF阅读器对象
            pdf_reader = PyPDF2.PdfReader(file)

            # 检查是否有密码
            if pdf_reader.is_encrypted:
                print("PDF 文件受到密码保护。")
                
                # 首先尝试使用传入的密码
                if password:
                    print(f"尝试使用提供的密码进行解密...")
                    if pdf_reader.decrypt(password):
                        print(f"使用提供的密码解密成功")
                    else:
                        print("提供的密码不正确，尝试空密码...")
                        if pdf_reader.decrypt(''):
                            print("使用空密码解密成功")
                        else:
                            print("空密码解密失败，尝试字典破解...")
                            found_password = crack_pdf_password(input_file, dictionary_folder)
                            if found_password:
                                if pdf_reader.decrypt(found_password.strip()):
                                    print(f"使用字典找到的密码 '{found_password.strip()}' 解密成功")
                                else:
                                    print(f"字典密码 '{found_password.strip()}' 解密失败")
                                    raise Exception("File has not been decrypted")
                            else:
                                print("未找到有效密码")
                                raise Exception("No valid password found")
                else:
                    print("尝试使用空密码进行解密...")
                    if pdf_reader.decrypt(''):
                        print("解密成功。")
                    else:
                        print("解密失败。尝试字典破解...")
                        found_password = crack_pdf_password(input_file, dictionary_folder)
                        if found_password:
                            if pdf_reader.decrypt(found_password.strip()):
                                print(f"使用密码 '{found_password.strip()}' 解密成功")
                            else:
                                print(f"密码 '{found_password.strip()}' 解密失败")
                                raise Exception("File has not been decrypted")
                        else:
                            print("未找到有效密码")
                            raise Exception("No valid password found")

            # 创建一个PDF编写器对象
            pdf_writer = PyPDF2.PdfWriter()

            # 将每一页添加到PDF编写器对象
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                pdf_writer.add_page(page)

            # 将解密的PDF内容写入新文件
            with open(output_file, 'wb') as output:
                pdf_writer.write(output)

        print(f"解密成功，已生成新文件：{output_file}")

    except Exception as e:
        print(f"发生错误：{e}")

def set_encrypt_pdf(input_file, output_file, password):
    """
    为PDF文件添加密码保护
    """
    try:
        # 创建 PDF 文件读取器对象
        with open(input_file, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)

            # 检查是否已加密
            if pdf_reader.is_encrypted:
                print("PDF 文件已受到密码保护。")
                return
            
            # 创建一个PDF编写器对象
            pdf_writer = PyPDF2.PdfWriter()

            # 将每一页添加到PDF编写器对象
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                pdf_writer.add_page(page)

            # 为 PDF 文件添加用户密码（user password）
            pdf_writer.encrypt(password)

            # 将加密后的 PDF 内容写入新文件
            with open(output_file, 'wb') as output:
                pdf_writer.write(output)

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
    
    args = parser.parse_args()
    
    if args.action == 'encrypt':
        if not args.password:
            print("错误：加密操作需要指定密码，请使用 -p 参数")
            exit(1)
        print(f"正在加密文件：{args.input} -> {args.output}")
        set_encrypt_pdf(args.input, args.output, args.password)
    
    elif args.action == 'decrypt':
        print(f"正在解密文件：{args.input} -> {args.output}")
        remove_pdf_password(args.input, args.output, args.dictionary, args.password)
