export default function TestCrypto({ data }) {
    return (
      <div style={{ padding: "2rem", fontFamily: "Arial" }}>
        <h1>💰 Test API Crypto</h1>
        <p>Precio de BTC/USDT desde el backend:</p>
        <pre>{JSON.stringify(data, null, 2)}</pre>
      </div>
    );
  }
  
  export async function getServerSideProps() {
    try {
      const res = await fetch("http://127.0.0.1:8000/api/crypto?symbol=BTCUSDT");
      const data = await res.json();
      return { props: { data } };
    } catch (error) {
      return { props: { data: { error: "No se pudo conectar al backend" } } };
    }
  }
  