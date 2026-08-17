# AROMA RILITH セラピスト専用給与清算ポータル

aroma Rilith 様向け、キャスカン (caskan) 連動型の給与清算・リアルタイム予約確認 PWA アプリケーションです。

## 🌟 特徴・機能
1. **アプリ立ち上げ・リロード時オンデマンド取得**:
   - 画面アクセス時およびキャスト切り替え時に最新の顧客予約データを一括パースします。
2. **時間の早い順ソート**:
   - 予約が時間の早い順（例: 22:50 → 24:50 → 27:40）に綺麗にソート表示されます。
3. **URLによるキャスト固定アクセス**:
   - `?cast=キャスト名` (例: `https://your-app.vercel.app/?cast=森永ここあ`) でアクセスすると、対象キャストに固定ロック表示されます。
4. **本指名数自動スライド歩合 (50%〜70%) & Bコース4,000円別枠全額バック**:
   - 本指名本数に応じた歩合率 (50%〜70%) を全自動計算。ラグジュアリーBコース代金から4,000円を差し引いた基礎売上に歩合率を適用します。
5. **給与清算確定 & LINE一括送信**:
   - ワンタップで当日の確定給与・店舗純売上（店落ち）を算出し、全明細をフォーマットしたテキストをコピーしてLINEへ送信できます。

---

## 🚀 Vercel への無料デプロイ手順 (完全無料 Hobby プラン)

### 1. GitHub リポジトリを作成してコードをプッシュ
プロジェクトディレクトリで以下を実行して GitHub にコミット・プッシュします。

```bash
git init
git add .
git commit -m "Initial commit for aroma Rilith payroll app"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/caskan-pwa-notifier.git
git push -u origin main
```

### 2. Vercel にログイン・連携
1. [Vercel公式サイト](https://vercel.com/) にアクセスし、無料登録（GitHubアカウントでログイン）します。
2. ダッシュボード画面で **[Add New...]** → **[Project]** を選択します。
3. GitHub リポジトリ `caskan-pwa-notifier` を選択して **[Import]** をクリックします。

### 3. 環境変数の設定 (Environment Variables)
デプロイ設定画面の **Environment Variables** に以下を追加します（任意）:

* `CASKAN_USER`: `staff`
* `CASKAN_PASS`: `arlt534`
* `CASKAN_SHOP`: `rilith`

### 4. Deploy ボタンを押す
**[Deploy]** ボタンを押すと約1分でデプロイが完了し、`https://caskan-pwa-notifier.vercel.app` のような無料URLが発行されます！
