import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"RVJgeBd2Hjx6","alg":"RS256","n":"tRzXMxpOa6QI9P3os1uYy-gpSZ2Tz0TkocwwCQ2azoqio_WS","e":"AQAB"}
const key24 = {"kty":"RSA","kid":"RVJgeBd2Hjx6","alg":"RS256","n":"tRzXMxpOa6QI9P3os1uYy-gpSZ2Tz0TkocwwCQ2azoqio_WS","e":"AQAB"};
void importJWK(key24, 'RS256');
