# PDF Password Tool

一个用于PDF文件加密和解密的Python工具，支持命令行参数操作。

## 功能特性

- 🔒 **PDF加密**：为PDF文件添加密码保护
- 🔓 **PDF解密**：移除PDF文件的密码保护
- 🗝️ **智能解密**：支持多种解密方式（已知密码、空密码、字典破解）
- 📚 **字典破解**：集成强大的密码字典库
- 🖥️ **命令行界面**：支持灵活的参数配置

## 安装依赖

```bash
pip install PyPDF2 pikepdf tqdm
```

## 命令行参数

### 基本语法
```bash
python main.py <action> -i <input_file> -o <output_file> [options]
```

### 参数说明

| 参数 | 缩写 | 必需 | 说明 |
|------|------|------|------|
| `action` | - | 是 | 操作类型：`encrypt`（加密）或 `decrypt`（解密） |
| `-i, --input` | `-i` | 是 | 输入PDF文件路径 |
| `-o, --output` | `-o` | 是 | 输出PDF文件路径 |
| `-p, --password` | `-p` | 加密时必需 | 密码（加密时必需，解密时可选） |
| `-d, --dictionary` | `-d` | 否 | 密码字典文件夹路径（默认：`./password_brute_dictionary`） |

## 使用示例

### 1. 加密PDF文件
```bash
# 为PDF文件添加密码保护
python main.py encrypt -i test.pdf -o encrypted.pdf -p mypassword123
```

### 2. 解密PDF文件（使用已知密码）
```bash
# 使用已知密码解密PDF文件
python main.py decrypt -i encrypted.pdf -o decrypted.pdf -p mypassword123
```

### 3. 解密PDF文件（使用字典破解）
```bash
# 使用字典破解PDF密码
python main.py decrypt -i encrypted.pdf -o decrypted.pdf -d ./password_brute_dictionary
```

### 4. 解密PDF文件（自动尝试）
```bash
# 自动尝试空密码和字典破解
python main.py decrypt -i encrypted.pdf -o decrypted.pdf
```

## 解密流程说明

解密操作会按照以下顺序尝试：

1. **使用提供的密码**（如果通过 `-p` 参数指定）
2. **尝试空密码**（如果PDF仅设置了编辑权限密码）
3. **字典破解**（使用指定的字典文件夹）

## 密码字典

项目集成了 [zxcvbn001/password_brute_dictionary](https://github.com/zxcvbn001/password_brute_dictionary) 字典库，包含：

- **键盘组合字典**：常见的键盘输入模式
- **拼音字典**：中文拼音组合
- **字母数字混合字典**：常见的密码组合

## 技术说明

### PDF密码类型

PDF文件支持两种密码类型：

- **用户密码（User Password）**：打开密码，限制对PDF文件的访问
- **所有者密码（Owner Password）**：权限密码，控制对PDF文件的操作权限

### 依赖库

- **PyPDF2**：用于PDF文件的读写和基本加密解密操作
- **pikepdf**：用于密码破解和高级PDF操作
- **tqdm**：提供进度条显示

## 错误处理

- 加密时如果文件已加密，会提示并跳过操作
- 解密时会详细显示每一步的尝试结果
- 提供清晰的错误信息帮助排查问题

## 注意事项

- 加密操作会生成新的PDF文件，不会修改原始文件
- 解密操作需要读取权限，确保输入文件可访问
- 字典破解可能需要较长时间，取决于字典大小和密码复杂度

## 许可证

本项目基于MIT许可证开源。
