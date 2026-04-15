import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"q5swxbHbgZ80","alg":"RS256","n":"MJOSMnvr7mka-XD4Bj8EeQv9Y57j_G1S_HNT4RLfWiEIr9D8","e":"AQAB"}
const key42 = {"kty":"RSA","kid":"q5swxbHbgZ80","alg":"RS256","n":"MJOSMnvr7mka-XD4Bj8EeQv9Y57j_G1S_HNT4RLfWiEIr9D8","e":"AQAB"};
void importJWK(key42, 'RS256');
