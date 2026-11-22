# ☀️ Sunny Hub — 個人資訊中樞

語言學習（商用英文／日文 N1～N3）＋字典・文法＋ACGN（動畫／漫畫／遊戲／小說）＋ACGN 新聞＋週報＋單字庫，整合成一個網站。

- **完全免費**：GitHub Pages（網站）＋ GitHub Actions（排程）＋ Gemini API 免費層（翻譯整理）。
- **不綁 Claude、不綁公司帳號**：所有東西都在你自己的 GitHub（`lindor8787-sun`）裡。
- **手機／電腦都能開**：`https://lindor8787-sun.github.io/sunny-hub/`

---

## 一次性設定（約 15 分鐘）

### 1. 申請免費 Gemini API 金鑰
1. 用個人 Google 帳號登入 <https://aistudio.google.com/apikey>，按 **Create API key**。
2. **不要綁定付款方式（Billing）**。保持免費層，就不可能產生費用；額度用完只會暫時失敗，隔天自動恢復。
3. 複製金鑰。金鑰只貼進第 4 步的 GitHub Secret，**不要寫進任何檔案**。

### 2. 建立 GitHub Repo
1. 登入 GitHub（`lindor8787-sun`）→ 右上角 **＋ › New repository**。
2. 名稱填 `sunny-hub`，選 **Public**（公開 repo 的 Actions 與 Pages 完全免費）→ **Create repository**。

### 3. 上傳檔案
1. 在新 repo 頁面點 **uploading an existing file**。
2. 把解壓縮後 `sunny-hub` 資料夾**裡面的所有內容**（包含 `.github` 資料夾）拖進去 → **Commit changes**。
   - Windows 預設隱藏「.」開頭的資料夾：檔案總管 › 檢視 › 勾選「隱藏的項目」，確認 `.github` 有一起拖上去。
   - 上傳後 repo 首頁應該看得到：`.github`、`data`、`hub`、`scripts`、`fetch.py`、`index.html`、`requirements.txt`、`README.md`。

### 4. 設定金鑰（Secret）
Repo › **Settings › Secrets and variables › Actions › New repository secret**
- Name：`GEMINI_API_KEY`
- Secret：貼上第 1 步的金鑰 → **Add secret**

### 5. 開啟網站（Pages）
Repo › **Settings › Pages** › Source 選 **Deploy from a branch** › Branch 選 `main`、資料夾 `/ (root)` › **Save**。
1～2 分鐘後網址生效：`https://lindor8787-sun.github.io/sunny-hub/`（此時顯示的是範例資料）。

### 6. 手動執行三個工作（只要第一次）
Repo › **Actions**（若出現提示，先按 *I understand my workflows, go ahead and enable them*），左側依序點選並按 **Run workflow**：

| 順序 | 工作名稱 | 作用 | 時間 |
|---|---|---|---|
| ① | **資料來源自我檢測** | 從 GitHub 伺服器測試每個資料來源是否抓得到，結果顯示在網站「架構說明 › 資料來源狀態」 | 約 2 分鐘 |
| ② | **建置離線辭典** | 下載 ECDICT（英中）、JMdict（日英），讓字典離線也查得到 | 約 3～8 分鐘 |
| ③ | **Sunny Hub 每日更新**（modules 保持 `all`） | 第一次抓全部真實內容，取代範例資料 | 約 5～10 分鐘 |

完成後重新整理網站即可。之後全部自動執行。

---

## 自動排程（台北時間）

| 時間 | 內容 |
|---|---|
| 每天 09:07 | ACGN 四類別（含封面／截圖）＋ ACGN 新聞（含今日必看 3 則） |
| 平日 10:07 | 語言上午場（英文 4＋日文 5）＋字庫新增＋字典詳解 |
| 平日 17:07 | 語言下午場 |
| 每天 20:07 | ACGN 集數／章節更新＋新聞 |
| 週日 21:07 | 週報 |
| 每週一 08:37 | 資料來源自我檢測 |
| 每月 2 日 02:17 | 更新離線辭典 |

- 分鐘設在 07，是為了避開整點的排程尖峰（GitHub 整點排程常延遲）。尖峰時仍可能晚幾分鐘到幾十分鐘，屬正常現象。
- 排程只在 GitHub 上跑，跟你的電腦開不開機無關。
- 想改時間：同時修改 `.github/workflows/hub.yml` 的 `cron` 和 `fetch.py` 的 `SCHEDULE_MAP`（兩邊字串要一樣）。cron 用 UTC＝台北時間減 8 小時。
- GitHub 規定：公開 repo 若 **60 天完全沒有活動**，排程會被自動停用。本專案每天都會自動提交資料，正常情況不會發生；萬一被停用，到 Actions 頁面按 **Enable workflow** 即可。

---

## 資料從哪裡來

所有內容都來自公開、免金鑰的來源。Gemini 只負責把「已經抓到的文字」翻譯、摘要、整理成卡片，不會自己上網找，也被要求不得捏造。

| 模組 | 主要來源 | 備援 |
|---|---|---|
| 動畫 | AniList API（本季／上季／下季、最新集數、封面、串流平台） | Bangumi 放送表（中文名、中文簡介、封面） |
| 漫畫 | AniList 日漫／韓漫熱門；**連載更新**：無限動漫、漫畫人 | Jikan（MyAnimeList） |
| 遊戲 | Steam 新推出／即將推出（含截圖）；App Store 台灣免費榜的遊戲 | — |
| 小說 | 晉江文學城月榜（華文）、Naver Series 排行（韓國） | AniList 華文／韓國網路小說 |
| 新聞 | 巴哈姆特 GNN、4Gamers（台灣）；Anime News Network、Gematsu、Siliconera（國際） | 各來源互為備援 |
| 英文 | Harvard Business Review、BBC Learning English、VOA Learning English | 依序遞補 |
| 日文 | NHK ニュース（経済／主要）、Yahoo!ニュース（経済）；另加 AI 編寫的 N1～N3 商用文法卡 | 依序遞補 |
| 字典 | 站內詳解（Gemini）→ ECDICT／JMdict 離線辭典 → Free Dictionary／Wiktionary／MyMemory | 外部字典另開分頁 |

**重要說明**
- 「學習卡片的原文」一定是逐字取自真實文章（程式會比對，不符就改用文章第一句）。
- 新聞、作品的連結一律是來源網站的原始網址。
- 有些網站可能擋 GitHub 伺服器的連線。這就是 ① 自我檢測的用途：網站上會列出哪些來源 ✅、哪些 ❌，❌ 的模組會自動改用備援。
- 封面與截圖由原網站提供，網站只顯示連結、不下載保存，僅供個人瀏覽。

---

## 關於 Gemini（2026 年 10 月查證）

- 預設模型：`gemini-3.8-flash`；備援：`gemini-3.5-flash-lite`。兩者都在**免費層**。
- 每天約 15～20 次呼叫（每個模組一次批次處理；已整理過的作品不會重複送出），遠低於免費額度。
- **不使用「Google 搜尋 grounding」**：目前 Gemini 3 系列的搜尋 grounding 只開放付費層，用了就可能產生費用，所以本專案改為自己抓公開資料，Gemini 只做翻譯整理。
- Google 退役模型時：只要改 `.github/workflows/hub.yml` 裡 `GEMINI_MODEL` 那一行（`selftest.yml` 也一樣）。可用模型清單：<https://ai.google.dev/gemini-api/docs/models>
- 額度用完：該次只會降級（例如新聞只有摘要、沒有翻譯），網站照常運作，隔天恢復。
- 你的免費額度可在 <https://aistudio.google.com/rate-limit> 查看。

---

## 網站上的「立即執行」按鈕

網站本身不放 API 金鑰，所以以下按鈕會開啟你 repo 的「新增 Issue」頁面（標題已預填），按 **Submit new issue** 後，GitHub Actions 會在 1～2 分鐘內完成並自動關閉 Issue：

- 字典 › **🤖 請求 AI 完整詳解**（標題 `[dict] 字詞 (en|ja)`）
- 字根家族／N1～N3 文法 › **☁️ 從網路抓新的**（標題 `[lexicon] refresh fam|jlpt`）

只有 repo 擁有者（你本人）開的 Issue 才會執行，別人無法用掉你的額度。使用前需要在該裝置的瀏覽器登入 GitHub。

---

## 珍藏與單字庫

- 珍藏、單字庫存在**瀏覽器**（localStorage），不會上傳到任何地方。
- 換手機或電腦：在「珍藏」或「單字庫」頁按 **⬇ 匯出備份**，到新裝置按 **⬆ 匯入備份**（同一個檔案包含珍藏＋單字庫）。
- 清除瀏覽器資料會一併清掉，建議定期匯出備份。

---

## 檔案結構

```
sunny-hub/
├─ index.html                    網站（單一檔案）
├─ fetch.py                      主程式（依排程決定要跑的模組；--selftest 自我檢測）
├─ requirements.txt
├─ hub/
│   ├─ common.py                 HTTP、合併去重、繁簡轉換、狀態紀錄、Gemini 呼叫
│   ├─ acgn.py                   動畫／漫畫／遊戲／小說＋封面
│   ├─ news.py                   ACGN 新聞
│   ├─ lang.py                   英文／日文學習卡
│   ├─ lexicon.py                字根家族、JLPT 字庫
│   ├─ dictionary.py             站內詳解字典
│   ├─ weekly.py                 週報
│   └─ feeds.py                  RSS 讀取
├─ scripts/build_dict.py         離線辭典建置
├─ data/                         網站讀取的資料（排程自動更新，請勿手動改）
│   ├─ lang.json  acgn.json  news.json  lexicon.json  status.json
│   ├─ weekly/index.json
│   └─ dict/detail.json  dict/en/*.json  dict/ja/*.json
└─ .github/workflows/
    ├─ hub.yml                   每日排程＋網站按鈕（Issue）觸發
    ├─ selftest.yml              資料來源自我檢測
    └─ build-dict.yml            離線辭典建置
```

## 授權與來源標示
- ECDICT — MIT License（https://github.com/skywind3000/ECDICT）
- JMdict — © Electronic Dictionary Research and Development Group，CC BY-SA 4.0（https://www.edrdg.org/edrdg/licence.html），經 scriptin/jmdict-simplified 轉換
- 作品資料：AniList、Bangumi、Steam、Apple、晉江文學城、Naver Series、無限動漫、漫畫人；新聞版權屬各原始媒體。本站僅供個人學習瀏覽。

## 疑難排解
| 狀況 | 處理 |
|---|---|
| 網站一直是範例資料 | Actions › Sunny Hub 每日更新 › Run workflow；看執行紀錄是否有錯 |
| 某區塊沒更新 | 網站「架構說明 › 資料來源狀態」看該來源是否 ❌，錯誤訊息會寫原因 |
| 翻譯變成英文原文 | Gemini 額度用完或金鑰錯誤；檢查 Secret `GEMINI_API_KEY` |
| Actions 出現 `push` 失敗 | Settings › Actions › General › Workflow permissions 選 **Read and write permissions** |
| 字典查不到多數單字 | 確認 ② 建置離線辭典已執行成功 |
