const visualViewRoot = document.querySelector("#view");

function syncComparisonPeriod() {
  const start = visualViewRoot.querySelector("#visualStart");
  const end = visualViewRoot.querySelector("#visualEnd");
  const compareStart = visualViewRoot.querySelector("#compareStart");
  const compareEnd = visualViewRoot.querySelector("#compareEnd");
  if (!start || !end || !compareStart || !compareEnd || !compareStart.value) return;
  const dates = [...start.options].map((option) => option.value).filter(Boolean);
  const startIndex = start.value ? dates.indexOf(start.value) : 0;
  const endIndex = end.value ? dates.indexOf(end.value) : dates.length - 1;
  const periodLength = endIndex >= startIndex ? endIndex - startIndex + 1 : dates.length;
  const compareIndex = dates.indexOf(compareStart.value);
  [...compareStart.options].forEach((option) => {
    if (!option.value) return;
    const index = dates.indexOf(option.value);
    option.disabled = index < 0 || index + periodLength > dates.length;
  });
  const matchedEnd = dates[compareIndex + periodLength - 1] || "";
  if (matchedEnd && compareEnd.value !== matchedEnd) {
    compareEnd.value = matchedEnd;
    compareEnd.dispatchEvent(new Event("change", { bubbles: true }));
  }
}

visualViewRoot.addEventListener("change", (event) => {
  if (["visualStart", "visualEnd", "compareStart", "compareEnd"].includes(event.target.id)) setTimeout(syncComparisonPeriod, 0);
});
new MutationObserver(syncComparisonPeriod).observe(visualViewRoot, { childList: true, subtree: true });
