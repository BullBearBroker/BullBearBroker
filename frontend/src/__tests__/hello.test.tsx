import { render, screen } from "@testing-library/react";

function HelloWorld() {
  return <h1>Hola BullBearBroker 🚀</h1>;
}

describe("HelloWorld component", () => {
  it("renderiza el texto correctamente", () => {
    render(<HelloWorld />);
    expect(screen.getByText("Hola BullBearBroker 🚀")).toBeInTheDocument();
  });
});
