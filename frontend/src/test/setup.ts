import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Remove rendered components between tests so they can't leak into each other.
afterEach(() => cleanup());
