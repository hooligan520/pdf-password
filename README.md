# PDF Password Tool

一个用于PDF文件加密和解密的Python工具，支持命令行参数操作。

## 功能特性

- 🔒 **PDF加密**：为PDF文件添加密码保护
- 🔓 **PDF解密**：移除PDF文件的密码保护
- 🗝️ **智能解密**：支持多种解密方式（已知密码、空密码、字典破解）
- 📚 **字典破解**：集成强大的密码字典库
- 🖥️ **命令行界面**：支持灵活的参数配置
- ⚡ **多进程支持**：支持多进程并行破解

## 安装依赖

```bash
pip install pikepdf pyhanko
```

或者使用 requirements.txt：

```bash
pip install -r requirements.txt
```

## 命令行参数

### 基本语法

```bash
python main.py <action> -i <input_file> -o <output_file> [options]
```

### 参数说明

| 参数 | 缩写 | 必需 | 说明 |
|------|------|------|------|
| `action` | - | 是 | 操作类型：`encrypt`（加密）、`decrypt`（解密）或 `hash`（提取hash） |
| `-i, --input` | `-i` | 是 | 输入PDF文件路径 |
| `-o, --output` | `-o` | encrypt/decrypt时必需 | 输出PDF文件路径（hash操作不需要） |
| `-p, --password` | `-p` | 加密时必需 | 密码（加密时必需，解密时可选） |
| `-d, --dictionary` | `-d` | 否 | 密码字典文件夹路径（默认：`./password_brute_dictionary`） |
| `-t, --threads` | `-t` | 否 | 进程数（默认8，仅优化版本有效） |
| `-b, --batch-size` | `-b` | 否 | 批次大小（默认50，仅优化版本有效） |
| `--no-optimized` | - | 否 | 禁用优化版本，使用标准版本 |

## 使用示例

### 1. 加密PDF文件

```bash
# 为PDF文件添加密码保护
python main.py encrypt -i ./test/test.pdf -o ./test/encrypted.pdf -p mypassword123
```

### 2. 解密PDF文件（使用已知密码）

```bash
# 使用已知密码解密PDF文件
python main.py decrypt -i ./test/encrypted.pdf -o ./test/decrypted.pdf -p mypassword123
```

### 3. 解密PDF文件（使用字典破解）

```bash
# 使用字典破解PDF密码（默认使用优化版本，8进程）
python main.py decrypt -i ./test/encrypted.pdf -o ./test/decrypted.pdf -d ./password_brute_dictionary

# 自定义进程数和批次大小
python main.py decrypt -i ./test/encrypted.pdf -o ./test/decrypted.pdf -d ./password_brute_dictionary -t 4 -b 100

# 使用标准版本（单线程）
python main.py decrypt -i ./test/encrypted.pdf -o ./test/decrypted.pdf -d ./password_brute_dictionary --no-optimized
```

### 4. 解密PDF文件（自动尝试）

```bash
# 自动尝试空密码和字典破解
python main.py decrypt -i ./test/encrypted.pdf -o ./test/decrypted.pdf
```

### 5. 提取PDF Hash值（用于Hashcat/John the Ripper）

```bash
# 提取PDF的hash值，输出为John the Ripper / Hashcat格式
python main.py hash -i ./test/encrypted.pdf

# 输出示例：
# $pdf$2*3*40*0*1*16*0123456789abcdef*32*...*32*...
```

**使用提取的hash进行破解：**

```bash
# Hashcat (macOS需要安装hashcat)
hashcat -m 10500 hash.txt wordlist.txt

# John the Ripper
john --format=PDF hash.txt
```

## 解密流程说明

解密操作会按照以下顺序尝试：

1. **使用提供的密码**（如果通过 `-p` 参数指定）
2. **尝试空密码**（如果PDF仅设置了编辑权限密码）
3. **字典破解**（使用指定的字典文件夹，密码会自动去重和排序）

## 密码字典

项目集成了 [zxcvbn001/password_brute_dictionary](https://github.com/zxcvbn001/password_brute_dictionary) 字典库，包含：

- **键盘组合字典**：常见的键盘输入模式
- **拼音字典**：中文拼音组合
- **字母数字混合字典**：常见的密码组合

字典文件会自动去重，并按长度和字典序排序，短密码优先尝试。

## 技术说明

### PDF密码类型

PDF文件支持两种密码类型：

- **用户密码（User Password）**：打开密码，限制对PDF文件的访问
- **所有者密码（Owner Password）**：权限密码，控制对PDF文件的操作权限

### 依赖库

- **pikepdf**：用于PDF文件的读写、加密解密和密码破解操作
- **pyhanko**：用于提取PDF hash值（Hashcat/John the Ripper格式）

## 版本说明

工具支持两种运行模式：

- **优化版本（默认）**：使用多进程并行处理，支持自定义进程数和批次大小
- **标准版本**：使用单线程顺序处理，通过 `--no-optimized` 参数启用

### 性能对比

基于真实字典测试（523,171个密码，10秒测试）：

| 版本 | 速度 | 10秒内尝试密码数 | 特点 |
|------|------|-----------------|------|
| **优化版本（多进程）** | **~1,473 密码/秒** | ~14,950 个 | 多进程并行，充分利用多核CPU |
| **标准版本（单线程）** | ~318 密码/秒 | ~3,179 个 | 单线程顺序处理，资源占用低 |

**性能提升**：优化版本比标准版本快约 **4.6倍**

### 选择建议

- **使用优化版本**（默认）：适合大多数场景，特别是大字典破解
- **使用标准版本**：当系统资源有限或需要更稳定的单线程处理时

## 错误处理

- 加密时如果文件已加密，会提示并跳过操作
- 解密时会详细显示每一步的尝试结果
- 提供清晰的错误信息帮助排查问题

## 注意事项

- 加密操作会生成新的PDF文件，不会修改原始文件
- 解密操作需要读取权限，确保输入文件可访问
- 字典破解可能需要较长时间，取决于字典大小和密码复杂度
- 建议使用较小的测试字典进行功能验证
- 多进程模式会占用更多CPU资源，可根据系统情况调整进程数

## 许可证

本项目基于MIT许可证开源。
