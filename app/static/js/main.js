// 1) DOM References
const input        = document.getElementById("search-input");
const suggestions  = document.getElementById("suggestions");
const form         = document.getElementById("search-form");
const resultDiv    = document.getElementById("result-container");
const chartDiv     = document.getElementById("tv_chart");
const wrapper      = document.querySelector(".search-wrapper");
const secContainer = document.getElementById("sec-docs-container");
const newsContainer = document.createElement("div");

// 2) Debounce helper
function debounce(fn, ms = 200) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

// 3) Load tickers
let companies = [];
fetch("/static/data/company_tickers.json")
  .then(res => res.json())
  .then(data => {
    companies = Object.values(data).map(item => ({
      symbol: item.ticker,
      name:   item.title
    }));
  })
  .catch(err => console.error("Failed to load tickers:", err));

// 4) Typeahead
function showSuggestions(list) {
  suggestions.innerHTML = "";
  if (!list.length) {
    suggestions.style.display = "none";
    wrapper.classList.remove("has-suggestions");
    return;
  }
  wrapper.classList.add("has-suggestions");
  list.forEach(({ symbol, name }) => {
    const li = document.createElement("li");
    li.textContent = `${symbol} — ${name}`;
    li.onclick = () => handleSearch(symbol);
    suggestions.appendChild(li);
  });
  suggestions.style.display = "block";
}
const onType = debounce(() => {
  const q = input.value.trim().toUpperCase();
  if (!q || !companies.length) return showSuggestions([]);
  const matches = companies
    .filter(c =>
      c.symbol.startsWith(q) ||
      c.name.toUpperCase().startsWith(q)
    )
    .slice(0, 10);
  showSuggestions(matches);
}, 150);
input.addEventListener("input", onType);

// 5) Search handler + render chart + SEC UI + News
async function handleSearch(query) {
  document.body.classList.add("search-active");
  showSuggestions([]);

  const company = companies.find(c => c.symbol === query);
  resultDiv.textContent = company
    ? `${company.name} (${company.symbol})`
    : query;
  resultDiv.style.display = "block";

  chartDiv.innerHTML = "";
  chartDiv.style.display = "block";
  new TradingView.widget({
    width:               "100%",
    height:              chartDiv.clientHeight,
    symbol:              query,
    interval:            "D",
    timezone:            "Etc/UTC",
    theme:               "light",
    style:               "1",
    locale:              "en",
    toolbar_bg:          "#f1f3f6",
    enable_publishing:   false,
    allow_symbol_change: false,
    container_id:        "tv_chart"
  });

  await renderSecDocs(query);
  await renderStockNews(query);
  input.value = "";
}

form.addEventListener("submit", e => {
  e.preventDefault();
  const q = input.value.trim().toUpperCase();
  if (q) handleSearch(q);
});

// 6) Render SEC Documents with two-column layout (buttons and document links)
async function renderSecDocs(ticker) {
  secContainer.innerHTML = "";

  const btn = document.createElement("div");
  btn.className = "sec-button";
  btn.innerHTML = `
    <span>SEC Documents</span>
    <svg viewBox="0 0 24 24"><path d="M10 17l5-5-5-5v10z"/></svg>
  `;
  secContainer.appendChild(btn);

  const dropdown = document.createElement("div");
  dropdown.className = "sec-dropdown";
  secContainer.appendChild(dropdown);

  btn.onclick = () => {
    const open = dropdown.style.display === "block";
    dropdown.style.display = open ? "none" : "block";
    btn.classList.toggle("open", !open);
  };

  try {
    const res = await fetch(`/api/sec/sec_doc_urls?ticker=${encodeURIComponent(ticker)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const { filings } = await res.json();

    const grouped = filings.reduce((acc, f) => {
      const form = f.form.toUpperCase();
      (acc[form] = acc[form] || []).push(f);
      return acc;
    }, {});

    // Define document types to display as buttons
    const docTypes = ["8-K", "10-Q", "10-K", "6-K", "20-F"];
    // Filter to only include types that exist in the data
    const availableTypes = docTypes.filter(type => grouped[type] && grouped[type].length > 0);
    // Add any other document types that weren't in our predefined list
    const extraTypes = Object.keys(grouped).filter(type => !docTypes.includes(type));
    const allTypes = [...availableTypes, ...extraTypes];
    
    // Create two-row layout container
    const twoRowContainer = document.createElement("div");
    twoRowContainer.className = "sec-two-row";
    dropdown.appendChild(twoRowContainer);
    
    // Create top row for buttons with horizontal scroll
    const buttonsRow = document.createElement("div");
    buttonsRow.className = "sec-buttons-row";
    twoRowContainer.appendChild(buttonsRow);
    
    // Create bottom row for document links
    const docsRow = document.createElement("div");
    docsRow.className = "sec-docs-row";
    twoRowContainer.appendChild(docsRow);
    
    // Default active document type
    let activeType = allTypes.length > 0 ? allTypes[0] : null;
    
    // Function to render document links for selected type
    const renderDocLinks = (type) => {
      docsRow.innerHTML = "";
      
      if (!grouped[type] || grouped[type].length === 0) {
        const emptyMsg = document.createElement("div");
        emptyMsg.textContent = `No ${type} documents available`;
        emptyMsg.style.padding = "12px 0";
        emptyMsg.style.color = "#666";
        docsRow.appendChild(emptyMsg);
        return;
      }
      
      grouped[type].forEach(doc => {
        const row = document.createElement("div");
        row.className = "sec-doc-row";
        
        const link = document.createElement("a");
        link.href = doc.url;
        link.target = "_blank";
        link.textContent = `${doc.form} — ${doc.report_date}`;
        
        row.appendChild(link);
        docsRow.appendChild(row);
      });
    };
    
    // Create buttons for each document type
    allTypes.forEach(type => {
      const button = document.createElement("button");
      button.textContent = type;
      button.onclick = () => {
        // Update active button
        buttonsRow.querySelectorAll("button").forEach(b => b.classList.remove("active"));
        button.classList.add("active");
        
        // Update document links
        renderDocLinks(type);
        activeType = type;
      };
      
      // Set active state for default type
      if (type === activeType) {
        button.classList.add("active");
      }
      
      buttonsRow.appendChild(button);
    });
    
    // Render initial document links
    if (activeType) {
      renderDocLinks(activeType);
    }
  }
  catch (err) {
    console.error("SEC fetch error:", err);
    secContainer.innerHTML = `
      <div style="color:#b00; padding:12px; font-size:0.9rem;">
        Failed to load SEC docs:<br/>
        <code>${err.message}</code>
      </div>
    `;
  }
}

// 7) Render Stock News in investing.com style
async function renderStockNews(ticker) {
  // 기존 뉴스 컨테이너가 있으면 제거
  const existingNews = document.querySelector(".news-container");
  if (existingNews) {
    existingNews.remove();
  }
  
  // 뉴스 컨테이너 초기화
  newsContainer.className = "news-container";
  newsContainer.innerHTML = "";
  
  // 뉴스 헤더 생성
  const newsHeader = document.createElement("div");
  newsHeader.className = "news-header";
  newsHeader.innerHTML = `
    <h2>Stock Market News</h2>
    <svg class="info-icon" viewBox="0 0 24 24">
      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z" fill="#70757a"/>
    </svg>
  `;
  newsContainer.appendChild(newsHeader);
  
  // 뉴스 목록 컨테이너
  const newsList = document.createElement("div");
  newsList.className = "news-list";
  newsContainer.appendChild(newsList);
  
  try {
    // 뉴스 API 호출
    const res = await fetch(`/api/news/stock_news?ticker=${encodeURIComponent(ticker)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    
    if (!data.news || data.news.length === 0) {
      newsList.innerHTML = `<div style="padding:16px; color:#666;">No news available for ${ticker}</div>`;
      document.querySelector(".center-container").appendChild(newsContainer);
      return;
    }
    
    // 뉴스 항목 렌더링
    data.news.forEach(item => {
      // 날짜 포맷팅
      const pubDate = new Date(item.published);
      const timeAgo = getTimeAgo(pubDate);
      
      // 뉴스 항목 생성
      const newsItem = document.createElement("a");
      newsItem.className = "news-item";
      newsItem.href = item.link;
      newsItem.target = "_blank"; // 새 탭에서 열기
      
      // 이미지 URL이 없는 경우 기본 이미지 사용
      const imageUrl = item.image_url || "https://via.placeholder.com/150x100.png?text=News";
      
      newsItem.innerHTML = `
        <img class="news-image" src="${imageUrl}" alt="${item.title}" onerror="this.src='https://via.placeholder.com/150x100.png?text=News'">
        <div class="news-content">
          <h3 class="news-title">${item.title}</h3>
          <p class="news-summary">${item.summary}</p>
          <div class="news-meta">
            <span class="news-source">${item.source}</span>
            <span class="news-time">${timeAgo}</span>
          </div>
        </div>
      `;
      
      newsList.appendChild(newsItem);
    });
    
    // 뉴스 컨테이너를 메인 컨테이너에 추가
    document.querySelector(".center-container").appendChild(newsContainer);
  }
  catch (err) {
    console.error("News fetch error:", err);
    newsList.innerHTML = `
      <div style="color:#b00; padding:12px; font-size:0.9rem;">
        Failed to load news:<br/>
        <code>${err.message}</code>
      </div>
    `;
    document.querySelector(".center-container").appendChild(newsContainer);
  }
}

// 시간 경과 표시 헬퍼 함수
function getTimeAgo(date) {
  const now = new Date();
  const diffMs = now - date;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  
  if (diffHour > 23) {
    return `${Math.floor(diffHour / 24)} days ago`;
  }
  if (diffHour > 0) {
    return `${diffHour} hour${diffHour > 1 ? 's' : ''} ago`;
  }
  if (diffMin > 0) {
    return `${diffMin} minute${diffMin > 1 ? 's' : ''} ago`;
  }
  return 'just now';
}

// 7) Click outside to close only the search dropdown
document.addEventListener("click", e => {
  if (!wrapper.contains(e.target)) {
    showSuggestions([]);
  }
});
