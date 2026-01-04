# export_chatgpt_to_md.py

ChatGPTの **公式データエクスポート（conversations.json）** を、検索・保管しやすい **Markdown（.md）** に変換するスクリプトです。

## 特徴

- ✅ ChatGPT公式エクスポートの `conversations.json` に対応
- ✅ 変換モード
  - `per_month`：**月ごと（YYYY-MM）**に束ねて出力
  - `per_chat`：会話ごとに1ファイルで出力
- ✅ 出力は UTF-8 の Markdown
- ✅ オフライン実行（外部API不要）

---

## 使い方

### 1) ChatGPTからデータをエクスポートする

ChatGPTの設定から **Export data** を実行し、届いたZIPを解凍します。  
解凍後、以下のファイルが含まれます：

- `conversations.json`

> ※ エクスポート方法のUIは変更される可能性があります。  
> 必要に応じて「ChatGPT Export data」で検索してください。

---

### 2) 変換する

```bash
python export_chatgpt_to_md.py conversations.json --mode per_month -o out_md
````

> Windowsで `python` が通らない場合は `py` をお試しください：

```powershell
py .\export_chatgpt_to_md.py .\conversations.json --mode per_month -o .\out_md
```

---

## コマンド例

### 月ごとにまとめて出力（おすすめ）

```bash
python export_chatgpt_to_md.py conversations.json --mode per_month -o out_md
```

出力例：

```
out_md/
  2025-12_chatgpt_bundle.md
  2026-01_chatgpt_bundle.md
  ...
```

### 会話ごとに出力

```bash
python export_chatgpt_to_md.py conversations.json --mode per_chat -o out_md
```

出力例：

```
out_md/
  20260103_MyTitle_ab12cd34.md
  20251230_OtherTitle_ef56gh78.md
  ...
```

---

## オプション

|オプション|説明|例|
|---|---|---|
|`conversations_json`|入力ファイル（必須）|`conversations.json`|
|`-o, --out`|出力ディレクトリ|`-o out_md`|
|`--mode`|出力モード（`per_month` / `per_chat`）|`--mode per_chat`|

---

## 制限事項 / 注意

- ChatGPTのエクスポート形式は将来的に変更される可能性があります。
    
- 一部の会話はメッセージツリー構造の都合で、表示順の再現が完全でない場合があります。
    
- 変換結果に機密情報が含まれる場合があります。公開・共有時はご注意ください。
    

---

## 免責
本ソフトウェアは MIT License の条件に基づき「現状のまま」提供され、いかなる保証もありません。利用により生じた損害について、著作者は責任を負いません。

---

## 開発

依存ライブラリはありません（Python標準ライブラリのみ）。

動作確認の目安：

- Python 3.10+ 推奨（3.11/3.12でもOK）
    

---

## コントリビュート

Issue / PR 歓迎です。

---

## ライセンス

MIT License（`LICENSE` を参照）

---

## English (Short)

Convert ChatGPT exported `conversations.json` into Markdown files.

```bash
python export_chatgpt_to_md.py conversations.json --mode per_month -o out_md
```

Modes:

- `per_month`: bundle by `YYYY-MM`
    
- `per_chat`: one file per conversation
    

