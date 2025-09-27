export default async function TestForex() {
  try {
    const res = await fetch(
      "http://127.0.0.1:8000/api/markets/forex/rates?pairs=EURUSD",
      { cache: "no-store" }
    );
    const data = await res.json();

    return (
      <div style={{ padding: "2rem", fontFamily: "Arial" }}>
        <h1>💱 Test API Forex</h1>
        <p>Par EUR/USD desde el backend:</p>
        <pre>{JSON.stringify(data, null, 2)}</pre>
      </div>
    );
  } catch (error) {
    return (
      <div style={{ padding: "2rem", fontFamily: "Arial" }}>
        <h1>💱 Test API Forex</h1>
        <p>Error: no se pudo conectar al backend</p>
      </div>
    );
  }
}
