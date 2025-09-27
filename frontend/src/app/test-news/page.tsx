export default async function TestNews() {
  try {
    const res = await fetch("http://127.0.0.1:8000/api/news/latest", {
      cache: "no-store",
    });
    const data = await res.json();

    return (
      <div style={{ padding: "2rem", fontFamily: "Arial" }}>
        <h1>📰 Test API News</h1>
        <p>Últimas noticias de mercado:</p>
        <pre>{JSON.stringify(data, null, 2)}</pre>
      </div>
    );
  } catch (error) {
    return (
      <div style={{ padding: "2rem", fontFamily: "Arial" }}>
        <h1>📰 Test API News</h1>
        <p>Error: no se pudo conectar al backend</p>
      </div>
    );
  }
}
