import { customRender, screen } from "@/tests/utils/renderWithProviders";

function HelloWorld() {
  return <h1>Hola BullBearBroker 🚀</h1>;
}

describe("HelloWorld component", () => {
  it("renderiza el texto correctamente", () => {
    customRender(<HelloWorld />);
    expect(screen.getByText("Hola BullBearBroker 🚀")).toBeInTheDocument();
  });
});
