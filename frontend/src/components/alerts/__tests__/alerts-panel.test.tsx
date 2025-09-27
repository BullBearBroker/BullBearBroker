import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import useSWR from "swr";

import { AlertsPanel } from "../alerts-panel";

jest.mock("swr");

const mockedUseSWR = useSWR as jest.MockedFunction<typeof useSWR>;

const mutateMock = jest.fn();

jest.mock("@/lib/api", () => ({
  listAlerts: jest.fn(),
  createAlert: jest.fn(),
  deleteAlert: jest.fn(),
  sendAlertNotification: jest.fn(),
  suggestAlertCondition: jest.fn(),
  updateAlert: jest.fn(),
}));

describe("AlertsPanel condition helpers", () => {
  beforeEach(() => {
    mutateMock.mockReset();
    mockedUseSWR.mockReturnValue({
      data: [],
      error: undefined,
      mutate: mutateMock,
      isLoading: false,
    } as never);
  });

  it("prefills a quick condition only when the textarea is empty", async () => {
    const user = userEvent.setup();
    render(<AlertsPanel token="demo-token" />);

    const textarea = screen.getByPlaceholderText(/condición/i) as HTMLTextAreaElement;
    const helperButton = screen.getByRole("button", { name: /menor que/i });

    expect(textarea).toHaveValue("");
    expect(helperButton).toBeEnabled();

    await act(async () => {
      await user.click(helperButton);
    });

    expect(textarea).toHaveValue("<");
    expect(helperButton).toBeDisabled();
  });

  it("keeps custom expressions in the textarea as the source of truth", async () => {
    const user = userEvent.setup();
    render(<AlertsPanel token="demo-token" />);

    const textarea = screen.getByPlaceholderText(/condición/i) as HTMLTextAreaElement;
    const helperButton = screen.getByRole("button", { name: /menor que/i });

    await act(async () => {
      await user.type(textarea, "Precio cruza 30k");
    });

    expect(textarea).toHaveValue("Precio cruza 30k");
    expect(helperButton).toBeDisabled();

    await act(async () => {
      await user.click(helperButton);
    });

    expect(textarea).toHaveValue("Precio cruza 30k");

    await act(async () => {
      await user.clear(textarea);
    });

    expect(textarea).toHaveValue("");
    expect(helperButton).toBeEnabled();

    await act(async () => {
      await user.click(helperButton);
    });

    expect(textarea).toHaveValue("<");
  });
});
