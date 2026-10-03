# HJ212 Parser

软件工程实验一程序：Python HJ212-2017 环保协议单条报文解析器。

## 功能

- `is_valid_message(message)`：验证 `## + 4位长度 + 数据段 + 4位CRC + CRLF` 及字段结构。
- `validate_crc(message)`：按初值 `0xFFFF`、多项式 `0xA001` 校验数据段 CRC16。
- `parse_data_segment(message)`：返回报文头字段和原始 `CP` 字符串。
- `extract_monitoring_data(message)`：提取 `CP` 中形如 `w01001-Rtd=7.25` 的监测因子。

本项目只负责单条完整报文，不负责网络接收、粘包和分包重组；未知字段会被保留，不擅自推断单位。它是课程所需的结构解析器，不是完整协议一致性认证工具，不检查所有命令码对应的必填字段、时间合法性或设备业务规则。

### 接口约定

- 输入为 ASCII `str` 或 `bytes`，必须包含真实的 `\r\n` 结尾，而不是四个可见字符。数据段最多 1024 字节。
- `is_valid_message` 检查结构，不比较 CRC；`validate_crc` 检查封装及 CRC，不检查全部字段语义。需要安全解析时调用后两个必需方法，它们会同时检查结构及 CRC。
- `parse_data_segment` 保留顶层字段和去掉 `&&` 的 CP 字符串；额外接口 `parse_cp_fields` 返回 CP 内全部键值，避免与报文头同名字段互相覆盖。
- CP 支持分号与逗号分隔；拒绝重复键、空值和不完整分隔符。空 CP `CP=&&&&` 可以解析。
- `Rtd`、`Avg`、`Min`、`Max`、`Cou` 转换为 `Decimal`；`Flag` 和其他属性保留字符串。非法数值不会被默默转成零。
- 解析失败抛出 `MessageError`；两个布尔校验方法对非法输入返回 `False`。
- CRC 按题目指定参数实现，反射多项式 `0xA001`、初值 `0xFFFF`、无最终异或，仅覆盖数据段。`123456789` 的校验值为 `4B37`。报文中使用四位十六进制文字表示 CRC。
- 示例数据、时间、设备标识和密码均为虚构测试数据，不是现场采集记录。示例 JSON 为保持精度将 Decimal 输出为字符串。

## 运行

使用 Python 3.9 或更新版本，无第三方依赖。在当前作业目录中先进入项目目录，再执行：

```bash
cd hj212-parser
python hello_world.py
python demo.py
python -m unittest discover -s tests -v
```

`demo.py` 不带参数时生成一个本地示例。也可传入包含 ASCII 报文的文件路径：

```bash
python demo.py message.txt
```

## 文件结构

```text
hj212-parser/
  hello_world.py       Hello World 程序
  demo.py              生成示例及文件解析入口
  hj212/
    __init__.py        对外接口
    parser.py          解析器实现
  tests/
    __init__.py
    test_parser.py     自动化回归测试
  .gitignore
  README.md
```

## 验证

自动化测试包含 17 个测试方法，覆盖已知 CRC 向量、错误封装、数据篡改、字段解析、监测数据提取、重复键、非法数字、长度上限、Hello World 和命令行文件输入。多个方法还包含多个异常输入子用例。生成报文的自校验不能代替实际设备兼容性测试，本项目未进行现场设备联调。

## Git 提交建议

只上传本项目目录，不要将别人的参考报告和整份讲义上传为自己的成果。以下命令需要你检查后实际执行；目前尚未初始化、提交或推送仓库。公开仓库不要放入真实密码、私钥或令牌。首次提交前请确认 Git 用户名和邮箱已配置。

```bash
git init
git add .
git commit -m "feat: implement HJ212 parser"
git branch -M main
git remote add origin "替换为你的公开仓库地址"
git push -u origin main
```

以上适用于新建的空远程仓库；已有远程历史时不要强推覆盖。若要展示多次提交，请按真实开发和修改过程分阶段提交，不要伪造历史。

IDEA 也可以直接打开该目录用于 Git 操作：先在 Settings / Version Control / Git 中测试 Git 路径，再在 Commit 窗口查看差异、选择文件并提交，最后 Push。Git 图形界面操作不要求 Python 插件；在 IDE 内运行 Python 则取决于 IDE 版本与插件支持，也可在 Terminal 中运行上述命令。提交、推送和远程公开访问需分别验证和截图。

## 参考与使用说明

课程任务：https://star.jmhui.com.cn/p1/366.html 。本实现依据任务中明确给出的报文封装和 CRC 参数，并使用 AI 辅助编写。提交前应自行运行、理解代码，并根据课程规定说明 AI 使用情况。

