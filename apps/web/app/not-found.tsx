import Link from "next/link";

export default function NotFound() {
  return (
    <main className="route-loading" dir="rtl">
      <h1>این صفحه رو پیدا نکردیم.</h1>

      <p>می‌تونی به صفحهٔ اصلی مودیگو برگردی.</p>

      <Link href="/">بازگشت به مودیگو</Link>
    </main>
  );
}
