const chartView = document.querySelector("#view");

function chartTooltip(chart) {
  let tooltip = chart.querySelector(".chart-tooltip");
  if (!tooltip) {
    tooltip = document.createElement("div");
    tooltip.className = "chart-tooltip";
    tooltip.setAttribute("role", "status");
    tooltip.hidden = true;
    chart.appendChild(tooltip);
  }
  return tooltip;
}

function placeChartTooltip(point) {
  const chart = point.closest(".chart");
  if (!chart) return;
  const tooltip = chartTooltip(chart);
  const chartBox = chart.getBoundingClientRect();
  const pointBox = point.getBoundingClientRect();
  const index = point.dataset.pointIndex;
  const points = [...chart.querySelectorAll(`[data-chart-point][data-point-index="${index}"]`)];
  const lines = points.map((item) => `<span>${item.dataset.series || "数据"}</span><b>${item.dataset.metric || "指标"}：${item.dataset.value || "--"}</b>`).join("");
  tooltip.innerHTML = `<strong>第 ${Number(index) + 1} 个数据点</strong><em>${point.dataset.date || "暂无日期"}</em>${lines}`;
  tooltip.hidden = false;
  const rawLeft = pointBox.left - chartBox.left + pointBox.width / 2 - tooltip.offsetWidth / 2;
  const left = Math.max(10, Math.min(rawLeft, chartBox.width - tooltip.offsetWidth - 10));
  const top = Math.max(10, pointBox.top - chartBox.top - tooltip.offsetHeight - 12);
  tooltip.style.left = `${left}px`;
  tooltip.style.top = `${top}px`;
}

chartView.addEventListener("pointermove", (event) => {
  const point = event.target.closest?.("[data-chart-point]");
  if (point) placeChartTooltip(point);
  else if (chartView.querySelector(".chart-tooltip")) chartView.querySelector(".chart-tooltip").hidden = true;
});
chartView.addEventListener("pointerleave", () => {
  const tooltip = chartView.querySelector(".chart-tooltip");
  if (tooltip) tooltip.hidden = true;
});
