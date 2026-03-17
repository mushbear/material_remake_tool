# 素材组合工具 (Material Remake Tool)

根据指定的剧情标签组合，从现有素材中提取对应场景，重新组合成新的素材文件。

## 功能特性

- ✅ **模块二**：场景信息提取 - 从JSON分析文件中提取场景信息
- ✅ **模块三**：场景组合方案生成 - 根据标签组合生成多个素材重组方案
- ✅ **模块四**：素材下载与组合 - 下载素材、提取场景、去除BGM、拼接新素材
- ⏸️ **模块一**：素材ID智能选择（待实现）

## 项目结构

```
material_remake_tool/
├── config/
│   └── config.json                       # 配置文件
├── scripts/
│   ├── module2_scene_extractor.py       # 模块二：场景提取
│   ├── module3_scheme_generator.py      # 模块三：方案生成
│   └── module4_material_composer.py     # 模块四：素材组合
├── data/
│   ├── output/                           # 输出数据目录
│   └── temp/                             # 临时文件目录
├── output/                               # 最终视频输出
├── material_list.csv                     # 素材元数据
├── sample.json                           # 场景数据格式示例
└── README.md
```

## 环境要求

- Python 3.7+
- ffmpeg（用于视频处理）
- 依赖库：requests

### 安装依赖

```bash
pip install requests
```

### 安装 ffmpeg

**macOS**:
```bash
brew install ffmpeg
```

**Ubuntu/Debian**:
```bash
sudo apt-get install ffmpeg
```

**Windows**:
从 [ffmpeg官网](https://ffmpeg.org/download.html) 下载并添加到PATH

## 快速开始

### 1. 配置文件

编辑 `config/config.json`：

```json
{
  "narrative_function_tags": [
    "F01-强开局/吸睛钩子",
    "F02-背景速递/设定交代",
    "F03-极限施压/受辱"
  ],
  "num_schemes": 10,
  "test_material_ids": ["1337589"],
  "json_source_dir": "./",
  "output_dir": "./output",
  "temp_dir": "./data/temp",
  "remove_bgm": true
}
```

### 2. 准备数据

将素材分析JSON文件放到项目目录下（或指定目录），格式参考 `sample.json`。

### 3. 运行流程

#### 步骤1：提取场景信息（模块二）

```bash
python scripts/module2_scene_extractor.py
```

**输出**: `data/output/scenes_data.json`

**参数**:
- `--config`: 配置文件路径
- `--material-ids`: 素材ID列表（覆盖配置文件）
- `--json-dir`: JSON文件所在目录
- `--output`: 输出文件路径

**示例**:
```bash
python scripts/module2_scene_extractor.py \
  --material-ids 1337589 1326824 \
  --json-dir ./data/json_files
```

#### 步骤2：生成组合方案（模块三）

```bash
python scripts/module3_scheme_generator.py
```

**输出**: `data/output/scene_combination_schemes.json`

**参数**:
- `--config`: 配置文件路径
- `--scenes-data`: 场景数据文件路径
- `--tags`: 标签组合（覆盖配置文件）
- `--num-schemes`: 生成方案数量
- `--seed`: 随机种子（用于可复现结果）

**示例**:
```bash
# 生成5个方案
python scripts/module3_scheme_generator.py --num-schemes 5

# 自定义标签组合
python scripts/module3_scheme_generator.py \
  --tags "F01-强开局/吸睛钩子" "F02-背景速递/设定交代" "F05-高潮打脸/绝地反击" \
  --num-schemes 3
```

#### 步骤3：下载并组合素材（模块四）

```bash
python scripts/module4_material_composer.py
```

**输出**: `output/remix_material_*.mp4`

**参数**:
- `--config`: 配置文件路径
- `--schemes`: 组合方案文件路径
- `--material-csv`: 素材列表CSV文件
- `--output-dir`: 输出目录
- `--temp-dir`: 临时文件目录
- `--no-bgm-removal`: 不去除BGM
- `--scheme-id`: 只处理指定方案

**示例**:
```bash
# 处理所有方案
python scripts/module4_material_composer.py

# 只处理方案1，不去除BGM
python scripts/module4_material_composer.py \
  --scheme-id 1 \
  --no-bgm-removal

# 指定输出目录
python scripts/module4_material_composer.py \
  --output-dir ./my_output
```

## 数据格式

### JSON场景分析文件格式

参考 `sample.json`，关键字段：

```json
{
  "material_id": "1337589",
  "video_url": "https://...",
  "result": {
    "segments": [
      {
        "segment_id": 1,
        "start_time": 0,
        "end_time": 23,
        "duration": 23,
        "narrative_function_tag": "F01-强开局/吸睛钩子",
        "plot_summary": "...",
        "main_location": "室外/雪地湖边"
      }
    ]
  }
}
```

### 素材列表CSV格式

`material_list.csv`：

```csv
id,material_name,video_url
1326824,素材名称,https://hwmat-enc.ikyuedu.com/...
1337589,素材名称,https://hwmat-enc.ikyuedu.com/...
```

### 组合方案格式

模块三生成的 `scene_combination_schemes.json`：

```json
[
  {
    "scheme_id": 1,
    "scenes": [
      {
        "scene_index": 1,
        "material_id": "1337589",
        "segment_id": 1,
        "start_time": 0,
        "end_time": 23,
        "narrative_function_tag": "F01-强开局/吸睛钩子"
      }
    ],
    "total_duration": 360,
    "num_scenes": 3
  }
]
```

## 常见问题

### 1. ffmpeg未找到

**错误**: `ffmpeg: command not found`

**解决**: 安装ffmpeg并确保在PATH中

### 2. 下载视频失败

**可能原因**:
- 网络问题
- URL无效或已过期
- 服务器限制访问

**解决**:
- 检查网络连接
- 验证 `material_list.csv` 中的URL是否有效
- 使用本地已有的视频文件

### 3. BGM去除效果不理想

当前使用简单的频率过滤（高通滤波器保留人声），效果有限。

**改进建议**:
- 使用专业AI音频分离工具：[Spleeter](https://github.com/deezer/spleeter) 或 [Demucs](https://github.com/facebookresearch/demucs)
- 或保留原声（使用 `--no-bgm-removal` 参数）

### 4. 内存/磁盘空间不足

**解决**:
- 清理 `data/temp/` 临时目录
- 减少同时处理的方案数量
- 使用 `--scheme-id` 参数逐个处理

## 开发计划

- [ ] 模块一：素材ID智能选择
- [ ] 优化BGM去除效果（集成Spleeter/Demucs）
- [ ] 支持更多视频格式
- [ ] 添加视频质量控制选项
- [ ] Web界面

## 许可证

MIT License

## 联系方式

如有问题或建议，请提交Issue。
