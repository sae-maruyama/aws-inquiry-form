# AWS サーバーレス お問い合わせフォーム

AWS サービスを使用したサーバーレスお問い合わせフォーム: S3 + CloudFront + API Gateway + Lambda + DynamoDB

## システム構成

```
Webフォーム (S3 + CloudFront) → API Gateway → Lambda → DynamoDB
https://blue-bird.blog         https://api-gateway-url
```
![alt text](images/arc.png)

## 前提条件

- AWS アカウント
- 取得済みドメイン（例：お名前.com で取得した blue-bird.blog）

## 【前提知識】CORS と CSP について

### CORS（Cross-Origin Resource Sharing）とは
- 目的: 異なるドメイン間での通信を許可する仕組み
- 必要な理由: `https://blue-bird.blog`（フォーム）から `https://api-gateway-url`（API）への通信は異なるオリジン間のため、ブラウザが標準でブロックする
- 設定方法: サーバー側（Lambda）がレスポンスヘッダーで「このドメインからのアクセスを許可する」と宣言

### CSP（Content Security Policy）とは
- 目的: XSS攻撃などのセキュリティリスクを防ぐ
- 必要性: なくても動作するが、セキュリティ向上のため推奨
- 設定方法: HTML側でメタタグにより「このページはどこへのリクエストを許可するか」を制限

### リクエストの流れ
1. ユーザーが `https://blue-bird.blog` でフォーム送信
2. CSP チェック: ブラウザが「connect-src」設定を確認し、API Gateway への接続を許可
3. JavaScript実行: `fetch()` で API Gateway にPOSTリクエスト送信
4. CORS チェック: Lambda が `Access-Control-Allow-Origin` ヘッダーを付けてレスポンス
5. 成功: ブラウザがレスポンスを JavaScript に渡す

### 設定箇所
- CORS: Lambda コード内の `cors_headers` + 環境変数 `CORS_ORIGIN`
- CSP: HTML の `<meta>` タグ内の `connect-src`


## セットアップ手順

### 1. DynamoDB テーブル作成

1. DynamoDB コンソールで「テーブルの作成」
2. テーブル名: `InquiryTable`
3. パーティションキー: `id` (String)
4. その他はデフォルト設定で作成

### 2. Lambda 関数作成

1. Lambda コンソールで「関数の作成」
2. 関数名: `UploadInquiry`
3. ランタイム: Python 
4. 実行ロール: DynamoDB への読み書き権限を追加

Lambda コード
[inquiry-lambda.py](https://github.com/sae-maruyama/inquiry-form/blob/c6c08c7054f8b4ad7e2b0aaaaea95fc0e267c617/inquiry-lambda.py) を参照

5. 環境変数の設定（重要：CORS設定）:
   - `TABLE_NAME`: `InquiryTable`
   - `CORS_ORIGIN`: `https://blue-bird.blog`（実際のドメインに変更）

CORS設定のポイント: 
- すべての `return` 文に `headers: cors_headers` を含める
- 環境変数で簡単にドメインを変更可能
- Lambda プロキシ統合では、API Gateway側ではなくLambda側でCORSを制御

### 3. API Gateway 作成

1. API Gateway コンソールで「REST API」を作成
2. リソース:
   - ルートリソース（/）に POST メソッドを作成
   - 統合タイプ: Lambda プロキシ統合
   - Lambda 関数: `UploadInquiry`を選択
3. デプロイ: ステージ名 `dev` で API をデプロイ
4. 呼び出し URL をメモ: `https://api-gateway-url`

### 4. S3 バケット作成

1. S3 コンソールでバケット作成
2. 静的ウェブサイトホスティングを有効化
3. インデックスドキュメント: `index.html`
4. パブリック読み取りアクセスをブロック

### 5. HTML フォーム作成

index.html:
[index.html](https://github.com/sae-maruyama/inquiry-form/blob/c6c08c7054f8b4ad7e2b0aaaaea95fc0e267c617/index.html) を参照

重要な置き換え箇所:
- `https://api-gateway-url` を実際の API Gateway URL に置き換える（2箇所）

CSP設定のポイント:
- `connect-src` に API Gateway URL を追加
- セキュリティ向上のため推奨だが、削除しても動作する

### 6. CloudFront Distribution 作成

1. CloudFront コンソールで Distribution 作成
2. オリジンドメイン: S3 バケットのバケットエンドポイントを使用
3. SSL 証明書: ACM で証明書を取得（us-east-1 リージョンで作成）
4. CNAME: カスタムドメイン名（blue-bird.blog）を追加

### 7. Route53 設定

1. Route53 コンソールでホストゾーン作成
2. ドメイン名: blue-bird.blog
3. A レコード作成:
   - 名前: blue-bird.blog
   - エイリアス: はい
   - エイリアス先: CloudFront Distribution
4. お名前.com 設定: ネームサーバーを Route53 のものに変更


## 動作確認手順
1. `https://blue-bird.blog` でフォームにアクセス
2. 全項目入力して送信
3. 成功メッセージとID表示を確認
4. DynamoDB テーブルでデータ保存確認

![alt text](images/form-image.png)
![alt text](images/dynamodb-table.png)

### よくある問題

| 問題 | 原因 | 解決方法 |
|------|------|----------|
| CORS エラー | Lambda の CORS_ORIGIN 環境変数未設定 | 環境変数を確認 |
| JavaScript が動作しない | キャッシュまたはCSPエラー | CloudFrontキャッシュ削除、ブラウザ強制リフレッシュ |
| API が見つからない | API Gateway URL 間違い | ステージの呼び出し URL を再確認 |