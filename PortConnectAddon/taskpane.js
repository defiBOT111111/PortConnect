Office.onReady((info) => {
  if (info.host === Office.HostType.Excel) {
    const btn = document.getElementById("check-btn");
    if (btn) {
      btn.onclick = handleCheckButtonClick;
    }
  }
});

/**
 * 照合ボタンが押された時の処理
 */
async function handleCheckButtonClick() {
  const resultArea = document.getElementById("result-area");
  resultArea.innerText = "処理中...";

  try {
    // 1. PDFファイルの取得
    const fileInput = document.getElementById("file-input");
    if (!fileInput.files || fileInput.files.length === 0) {
      alert("PDFファイルを選択してください。");
      resultArea.innerText = "";
      return;
    }
    const pdfFile = fileInput.files[0];

    // 2. Excelの選択セルから S/I データを取得
    let siData = {};
    await Excel.run(async (context) => {
      const range = context.workbook.getSelectedRange();
      range.load("values");
      await context.sync();

      siData = {
        values: range.values,
      };
    });

    // 3. Django サーバーへ送信
    const result = await sendToDjangoAPI(pdfFile, siData);

    // 4. 結果の表示
    if (result.has_discrepancies) {
      let msg = "【不一致が見つかりました】\n\n";
      result.discrepancies.forEach((d) => {
        msg += `・${d.field}: S/I(${d.si_value}) vs B/L(${d.bl_value})\n`;
      });
      resultArea.innerText = msg;
    } else {
      resultArea.innerText = "✅ S/IとDraft B/Lの内容は一致しています！";
    }
  } catch (error) {
    console.error("エラー:", error);
    resultArea.innerText = "エラーが発生しました: " + error.message;
  }
}

/**
 * Django バックエンドへ POST 送信する関数
 */
async function sendToDjangoAPI(pdfFile, siData) {
  const formData = new FormData();
  formData.append("file", pdfFile);
  formData.append("si_data", JSON.stringify(siData));

  // バックエンドURL (末尾スラッシュ必須)
  const response = await fetch(
    "https://127.0.0.1:8000/api/check-discrepancies/",
    {
      method: "POST",
      body: formData,
    },
  );

  if (!response.ok) {
    throw new Error(`サーバーエラー (HTTP status: ${response.status})`);
  }

  return await response.json();
}
