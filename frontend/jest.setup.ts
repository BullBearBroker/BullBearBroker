import "@testing-library/jest-dom";

const mockRouter: {
  push: jest.Mock;
  replace: jest.Mock;
  refresh: jest.Mock;
  prefetch: jest.Mock;
  back: jest.Mock;
  forward: jest.Mock;
} = {
  push: jest.fn(),
  replace: jest.fn(),
  refresh: jest.fn(),
  prefetch: jest.fn(),
  back: jest.fn(),
  forward: jest.fn()
};

jest.mock("next/navigation", () => ({
  useRouter: () => mockRouter
}));

beforeEach(() => {
  Object.values(mockRouter).forEach((fn) => fn.mockClear());
});
