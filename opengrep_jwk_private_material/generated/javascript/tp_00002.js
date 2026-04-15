import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"oct","kid":"y7h33yALo7Iu","alg":"HS256","k":"H9BkhogJ47h9qTN3HMCJKQfWkxq2Xn3NZkeUhmWJb7gFMKOWJrNWxZhBiR0qWksI"}
const key2 = {"kty":"oct","kid":"y7h33yALo7Iu","alg":"HS256","k":"H9BkhogJ47h9qTN3HMCJKQfWkxq2Xn3NZkeUhmWJb7gFMKOWJrNWxZhBiR0qWksI"};
void importJWK(key2, 'HS256');
