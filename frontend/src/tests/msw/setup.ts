import "whatwg-fetch";

import { server } from "./server";

// Ensure server lifecycle hooks are registered for the test environment.
void server;
