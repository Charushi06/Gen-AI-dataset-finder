let combinedCSV = null;

async function searchDatasets() {
  const keyword = document.getElementById("keywordInput").value.trim();
  const dropdown = document.getElementById("datasetDropdown");
  const output = document.getElementById("outputText");

  if (!keyword) {
    output.innerText = "⚠️ Please enter a keyword first.";
    return;
  }

  output.innerText = "🔍 Searching Kaggle and Hugging Face...";
  dropdown.innerHTML = '<option disabled selected>Loading datasets...</option>';

  try {
    const response = await fetch("https://gen-ai-dataset-finder-1.onrender.com", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: keyword })
    });

    .then(response => response.json())
    .then(data => {
        console.log(data.generated_text);  // Display generated text
    })
    .catch(error => console.error('Error:', error));

    const data = await response.json();
    dropdown.innerHTML = '<option disabled selected>Select a dataset...</option>';

    data.results.forEach((item, i) => {
      const option = document.createElement("option");
      option.value = item.url;
      option.text = `${item.title} (${item.source})`;
      dropdown.appendChild(option);
    });

    output.innerText = `✅ ${data.results.length} results found. Select a dataset.`;

  } catch (err) {
    console.error(err);
    output.innerText = "❌ Could not fetch datasets.";
  }
}

async function generateData() {
  const url = document.getElementById("datasetDropdown").value;
  const rows = document.getElementById("rowToggle").value;
  const output = document.getElementById("outputText");
  const downloadSection = document.getElementById("downloadSection");

  // Step 1: Validate inputs
  if (!url) {
    output.innerText = "⚠️ Select a dataset first.";
    return;
  }

  const parsedRows = parseInt(rows);
  if (isNaN(parsedRows) || parsedRows <= 0) {
    output.innerText = "⚠️ Enter a valid number of rows.";
    return;
  }

  // Step 2: Prepare request
  const requestBody = {
    url: url,
    rows: parsedRows,
  };
  console.log("📤 Sending request body:", requestBody);

  output.innerText = `⏳ Generating ${parsedRows} synthetic rows...`;
  downloadSection.style.display = "none";

  try {
    // Step 3: Send request
    const response = await fetch("http://localhost:5000/generate_rows_only", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
    });

    console.log(`🔁 Response Status: ${response.status} ${response.statusText}`);

    // Step 4: Read response as raw text
    const rawResponse = await response.text();
    console.log("📥 Raw response:", rawResponse);

    // Step 5: Check if status is bad
    if (!response.ok) {
      output.innerText = `❌ Server error: ${response.status}`;
      return;
    }

    // Step 6: Try to parse the JSON
    let data;
    try {
      data = JSON.parse(rawResponse);
    } catch (parseError) {
      console.error("❌ JSON parsing failed. Backend sent non-JSON:", rawResponse);
      output.innerText = "❌ Response was not valid JSON.";
      return;
    }

    // Step 7: Success!
    console.log("✅ Parsed JSON:", data);
    if (data.combined_csv) {  
  combinedCSV = data.combined_csv;
  downloadSection.style.display = "block";
  output.innerText = data.synthetic_csv;
} else if (data.error) {
  output.innerText = `❌ Error: ${data.error}`;
  downloadSection.style.display = "none";
} else {
  output.innerText = "❌ No data returned from server.";
  downloadSection.style.display = "none";
}


  } catch (err) {
    // Step 8: Catch network or code errors
    console.error("❌ Network or unexpected error:", err);
    output.innerText = "❌ Something went wrong while contacting the server.";
    downloadSection.style.display = "none";
  }
}

fetch('/generate_rows_only', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ url: selectedUrl, rows: numRows })
})
.then(res => res.json())
.then(data => {
  generatedCSV = data.synthetic_csv;  // show this on screen
  combinedCSV = data.combined_csv;    // use this for download

  // display generated rows
  document.getElementById("csvPreview").textContent = generatedCSV;

  // enable download button
  document.getElementById("downloadBtn").disabled = false;
});


async function generateSummary() {
  const url = document.getElementById("datasetDropdown").value;
  const output = document.getElementById("outputText");

  if (!url) {
    output.innerText = "⚠️ Select a dataset first.";
    return;
  }

  output.innerText = `⏳ Generating summary...`;

  try {
    const response = await fetch("http://localhost:5000/summarize_only", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url })
    });

    const data = await response.json();
    output.innerText = data.summary;

  } catch (err) {
    console.error(err);
    output.innerText = "❌ Something went wrong.";
  }
}

function downloadCSV() {
  if (!combinedCSV) return;

  const blob = new Blob([combinedCSV], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "merged_dataset.csv";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}
