import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"l2qUnjMbpVC2","alg":"RS256","n":"L0ocMneBhJ8TcMQFfMy4KsASXs3MlPS47ompCfrT54Yv8eQr","e":"AQAB"}
const key31 = {"kty":"RSA","kid":"l2qUnjMbpVC2","alg":"RS256","n":"L0ocMneBhJ8TcMQFfMy4KsASXs3MlPS47ompCfrT54Yv8eQr","e":"AQAB"};
void importJWK(key31, 'RS256');
