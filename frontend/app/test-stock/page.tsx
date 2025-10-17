export default async function TestStock() {
  try {
    const res = await fetch("http://127.0.0.1:8000/api/markets/stocks/quotes?symbols=AAPL", {
      cache: "no-store",
    });
    const data = await res.json();

    return (
      <div style={{ padding: "2rem", fontFamily: "Arial" }}>
        <h1>📈 Test API Stocks</h1>
        <p>Precio de AAPL desde el backend:</p>
        <pre>{JSON.stringify(data, null, 2)}</pre>
      </div>
    );
  } catch (error) {
    return (
      <div style={{ padding: "2rem", fontFamily: "Arial" }}>
        <h1>📈 Test API Stocks</h1>
        <p>Error: no se pudo conectar al backend</p>
      </div>
    );
  }
}
