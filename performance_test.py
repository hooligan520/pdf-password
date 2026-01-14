#!/usr/bin/env python3
"""
PDF密码破解性能测试脚本
用于对比不同优化模式的性能差异
"""

import time
import subprocess
import sys
import os

def run_performance_test(test_name, command_args):
    """运行性能测试并返回结果"""
    print(f"\n{'='*60}")
    print(f"开始测试: {test_name}")
    print(f"命令: python main.py {command_args}")
    print('='*60)
    
    start_time = time.time()
    
    try:
        # 运行命令并捕获输出
        result = subprocess.run(
            f"python main.py {command_args}", 
            shell=True, 
            capture_output=True, 
            text=True,
            timeout=300  # 5分钟超时
        )
        
        elapsed_time = time.time() - start_time
        
        # 分析输出结果
        output = result.stdout
        if result.returncode == 0:
            print("✅ 测试成功")
        else:
            print("❌ 测试失败")
        
        # 提取性能信息
        passwords_per_second = extract_passwords_per_second(output)
        
        print(f"执行时间: {elapsed_time:.2f}秒")
        if passwords_per_second:
            print(f"密码处理速度: {passwords_per_second:,} 密码/秒")
        
        return {
            'success': result.returncode == 0,
            'time': elapsed_time,
            'speed': passwords_per_second,
            'output': output
        }
        
    except subprocess.TimeoutExpired:
        elapsed_time = time.time() - start_time
        print(f"⏰ 测试超时 (运行时间: {elapsed_time:.2f}秒)")
        return {
            'success': False,
            'time': elapsed_time,
            'speed': 0,
            'output': 'Timeout'
        }
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        return {
            'success': False,
            'time': 0,
            'speed': 0,
            'output': str(e)
        }

def extract_passwords_per_second(output):
    """从输出中提取密码处理速度"""
    lines = output.split('\n')
    for line in lines:
        if 'it/s' in line:
            # 提取类似 "615.70it/s" 的速度值
            import re
            match = re.search(r'(\d+\.?\d*)it/s', line)
            if match:
                return float(match.group(1))
    return None

def main():
    """主测试函数"""
    # 检查测试文件是否存在
    if not os.path.exists('encrypted_test.pdf'):
        print("❌ 测试文件不存在，请先创建加密的测试文件")
        print("运行: python main.py encrypt -i test.pdf -o encrypted_test.pdf -p testpassword123")
        return
    
    # 测试配置
    test_cases = [
        {
            'name': '标准模式（多线程）',
            'command': 'decrypt -i encrypted_test.pdf -o test_result1.pdf -d ./test_dict -t 4'
        },
        {
            'name': '超高性能模式（进程池+批量验证）',
            'command': 'decrypt -i encrypted_test.pdf -o test_result2.pdf -d ./test_dict -t 4 --ultra-mode -b 50'
        },
        {
            'name': '超高性能模式（大批量）',
            'command': 'decrypt -i encrypted_test.pdf -o test_result3.pdf -d ./test_dict -t 8 --ultra-mode -b 200'
        }
    ]
    
    results = []
    
    print("📊 PDF密码破解性能对比测试")
    print("测试环境:", sys.platform)
    print("CPU核心数:", os.cpu_count())
    
    for test_case in test_cases:
        result = run_performance_test(test_case['name'], test_case['command'])
        results.append({
            'name': test_case['name'],
            **result
        })
    
    # 输出性能对比报告
    print(f"\n{'='*80}")
    print("📈 性能对比报告")
    print('='*80)
    
    for result in results:
        status = "✅ 成功" if result['success'] else "❌ 失败"
        speed_info = f"{result['speed']:,} 密码/秒" if result['speed'] else "N/A"
        print(f"{result['name']:30} | {status:10} | 时间: {result['time']:6.2f}秒 | 速度: {speed_info}")
    
    # 计算性能提升
    if len(results) >= 2 and results[0]['speed'] and results[1]['speed']:
        speedup = results[1]['speed'] / results[0]['speed']
        print(f"\n🚀 性能提升: 超高性能模式比标准模式快 {speedup:.1f} 倍")
        
        # 与Advanced PDF Password Recovery对比
        advanced_speed = 68669  # 来自用户提供的图片数据
        if results[1]['speed']:
            gap_ratio = advanced_speed / results[1]['speed']
            print(f"📊 与Advanced PDF Password Recovery的差距: {gap_ratio:.1f} 倍")
            print(f"💡 建议: 我们的脚本性能仍有提升空间，但已显著改善")

if __name__ == '__main__':
    main()