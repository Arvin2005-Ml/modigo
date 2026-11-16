document.getElementById('retry').addEventListener('click', () => {
  if (navigator.onLine) window.location.reload();
  else document.getElementById('status').textContent = 'هنوز ارتباط برقرار نشده؛ اتصال اینترنت رو بررسی کن.';
});
window.addEventListener('online', () => {document.getElementById('status').textContent = 'ارتباط برگشت؛ می‌تونی دوباره امتحان کنی.';});
