import time
import os
import subprocess
import sys

def test_performance():
    """测试优化后代码的性能"""
    print("🔍 开始性能测试...")
    
    # 准备测试文件
    test_pdf = "test_encrypted.pdf"
    output_pdf = "test_decrypted_speed_test.pdf"
    dictionary_folder = "./password_brute_dictionary"
    
    # 确保测试文件存在
    if not os.path.exists(test_pdf):
        print("❌ 测试文件不存在，请先创建加密的测试PDF文件")
        return
    
    # 创建一个大字典来测试性能
    large_dict_file = os.path.join(dictionary_folder, "large_test_dict.txt")
    if not os.path.exists(large_dict_file):
        print("📝 创建大字典文件用于性能测试...")
        with open(large_dict_file, 'w') as f:
            # 生成1000个测试密码
            for i in range(1000):
                # 各种类型的密码
                f.write(f"password{i}\n")
                f.write(f"123456{i}\n")
                f.write(f"test{i:04d}\n")
                f.write(f"admin{i}\n")
                if i < 100:  # 前100个是短密码
                    f.write(f"{i:02d}\n")
                    f.write(f"abc{i}\n")
        print(f"✅ 创建了包含{4*1000 + 200}个密码的测试字典")
    
    # 测试性能（使用大字典）
    print("\n📊 开始性能测试（使用大字典）...")
    start_time = time.time()
    
    try:
        # 运行解密命令（不使用已知密码，强制进行字典破解）
        result = subprocess.run([
            sys.executable, "main.py", "decrypt", 
            "-i", test_pdf, 
            "-o", output_pdf,
            "-d", dictionary_folder
        ], capture_output=True, text=True, timeout=30)
        
        elapsed_time = time.time() - start_time
        
        # 分析输出结果
        output_lines = result.stdout.split('\n')
        speed_info = None
        
        for line in output_lines:
            if '速度：' in line:
                speed_info = line.strip()
                break
        
        print(f"⏱️ 总耗时: {elapsed_time:.2f}秒")
        print(f"📈 性能结果: {speed_info if speed_info else '未找到速度信息'}")
        print(f"🔍 完整输出:")
        print(result.stdout)
        
        if result.stderr:
            print(f"❌ 错误输出:")
            print(result.stderr)
            
    except subprocess.TimeoutExpired:
        print("❌ 测试超时（30秒）")
    
    # 清理测试文件
    if os.path.exists(output_pdf):
        os.remove(output_pdf)
        print("🧹 已清理测试输出文件")

def create_performance_benchmark():
    """创建性能基准测试"""
    print("\n🎯 创建性能基准测试...")
    
    # 创建一个已知密码的加密文件用于基准测试
    test_pdf = "benchmark_encrypted.pdf"
    if not os.path.exists(test_pdf):
        print("📝 创建基准测试文件...")
        import pikepdf
        
        # 创建一个简单的PDF
        pdf = pikepdf.Pdf.new()
        page = pikepdf.Page(pdf)
        pdf.pages.append(page)
        
        # 使用已知密码加密
        password = "benchmark123"
        pdf.save(test_pdf, encryption=pikepdf.Encryption(user=password, owner=password))
        print(f"✅ 创建基准测试文件，密码为: {password}")
    
    # 创建基准测试字典
    benchmark_dict = os.path.join("./password_brute_dictionary", "benchmark_dict.txt")
    if not os.path.exists(benchmark_dict):
        with open(benchmark_dict, 'w') as f:
            # 在中间位置放置正确密码
            for i in range(500):
                f.write(f"wrong{i}\n")
            f.write("benchmark123\n")  # 正确密码在第501个位置
            for i in range(500, 1000):
                f.write(f"wrong{i}\n")
        print("✅ 创建基准测试字典（1000个密码，正确密码在第501个）")
    
    # 运行基准测试
    print("\n📊 运行基准测试...")
    start_time = time.time()
    
    try:
        result = subprocess.run([
            sys.executable, "main.py", "decrypt", 
            "-i", test_pdf, 
            "-o", "benchmark_decrypted.pdf",
            "-d", "./password_brute_dictionary"
        ], capture_output=True, text=True, timeout=60)
        
        elapsed_time = time.time() - start_time
        
        # 计算性能
        total_passwords = 1000
        speed = total_passwords / elapsed_time
        
        print(f"🎯 基准测试结果:")
        print(f"   - 总耗时: {elapsed_time:.2f}秒")
        print(f"   - 尝试密码数: {total_passwords}")
        print(f"   - 平均速度: {speed:.2f} 密码/秒")
        print(f"   - 是否达到目标600/s: {'✅' if speed >= 600 else '❌'} ({speed:.2f}/秒)")
        
        print(f"🔍 完整输出:")
        print(result.stdout)
        
    except subprocess.TimeoutExpired:
        print("❌ 基准测试超时")

if __name__ == "__main__":
    print("=" * 50)
    print("PDF密码破解性能测试")
    print("=" * 50)
    
    # 运行性能测试
    test_performance()
    
    # 运行基准测试
    create_performance_benchmark()