import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"HDPALtYkATei","alg":"RS256","n":"W-FckaXGX9_Zn4sb6NhcOaug3_FR3T5F2-_1DHMtwquiobXI","e":"AQAB","d":"H4sc5FRl"}
const key9 = {"kty":"RSA","kid":"HDPALtYkATei","alg":"RS256","n":"W-FckaXGX9_Zn4sb6NhcOaug3_FR3T5F2-_1DHMtwquiobXI","e":"AQAB","d":"H4sc5FRl"};
void importJWK(key9, 'RS256');
