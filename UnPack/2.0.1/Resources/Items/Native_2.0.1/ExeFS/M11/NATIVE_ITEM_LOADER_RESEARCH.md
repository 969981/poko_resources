# Pokopia 2.0.1 00983.bin 原生加载与 ID×68 静态候选

ExeFS sha256: 8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f
00983.bin sha256: 2a2dbc88715dc76410cef495d418613456c0c4fa7b7d719e7b37709ad53e1b6f

**仅候选，尚未证明 983 资源调用、记录基址和 ID×68 在同一数据流中。**

- main+0x726734 score=17 983=['0x726734'] 4600=[] stride=['0x7269e4']
- main+0x7269e4 score=17 983=['0x726734'] 4600=[] stride=['0x7269e4']
- main+0x150e90c score=17 983=['0x150edc4'] 4600=[] stride=['0x150e570', '0x150e90c', '0x150ec68', '0x150ec88', '0x150ed80', '0x150eda0', '0x150edc0', '0x150ede0']
- main+0x150ec68 score=17 983=['0x150edc4'] 4600=[] stride=['0x150e90c', '0x150ec68', '0x150ec88', '0x150ed80', '0x150eda0', '0x150edc0', '0x150ede0', '0x150f14c']
- main+0x150f14c score=17 983=['0x150edc4'] 4600=[] stride=['0x150ec68', '0x150ec88', '0x150ed80', '0x150eda0', '0x150edc0', '0x150ede0', '0x150f14c']
- main+0x30e1a4 score=16 983=[] 4600=['0x30e1a4'] stride=['0x30e38c']
- main+0x30e38c score=16 983=[] 4600=['0x30e1a4'] stride=['0x30e38c']
- main+0x1027f58 score=16 983=[] 4600=['0x1028234'] stride=['0x1027f58']
- main+0x1028234 score=16 983=[] 4600=['0x1028234'] stride=['0x1027f58']
- main+0x31ca24 score=15 983=['0x31ca24', '0x31ca40'] 4600=[] stride=[]
- main+0x3305b4 score=15 983=['0x3305b4'] 4600=[] stride=[]
- main+0x6d09cc score=15 983=['0x6d09cc'] 4600=[] stride=[]
- main+0x98a344 score=15 983=[] 4600=[] stride=['0x98a344']
- main+0xae2370 score=14 983=['0xae23fc'] 4600=[] stride=['0xae2370']
- main+0xe5a99c score=14 983=[] 4600=['0xe5a99c'] stride=[]
- main+0x1028968 score=14 983=[] 4600=['0x1028968'] stride=[]
- main+0x15389d8 score=14 983=['0x1538d4c'] 4600=[] stride=['0x15389d8']
- main+0x1538d4c score=14 983=['0x1538d4c'] 4600=[] stride=['0x15389d8']
- main+0x3a97e4 score=12 983=['0x3a97e4', '0x3a9800'] 4600=[] stride=[]
- main+0x59cbc0 score=12 983=[] 4600=[] stride=['0x59cbc0']

Next: resolve exact 983 asset call -> table base -> item ID indexing -> +0x22 field -> +0x26 / +0x3A consumer.
