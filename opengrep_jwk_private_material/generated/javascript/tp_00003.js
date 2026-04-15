import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"6wwtt1zI3X7v","alg":"RS256","n":"Pa_nJPfSFFtHpcRrh5yDDQNFJ-lULWMcCEDVUCzYqYpM3Mb7","e":"AQAB","p":"jwSHtfq1lRYzXwEocW0EbbvJqiT7oneiBzH7Qs8evtCq9NwG","q":"cdhw0Fi-Np_gtAtxKSBxkxmOMjbjkc_JG0tMHMQ7_BXRki2N","dp":"rlILC4Ms3ShkiTmj5Vd55-g7f0tGikhNjLYOi5kkHYsgjtj0","dq":"Zi76xGV9UkUKpLRVrksM2P5xL6Wi-aqwu1m-a3EfMmwEN70R"}
const key3 = {"kty":"RSA","kid":"6wwtt1zI3X7v","alg":"RS256","n":"Pa_nJPfSFFtHpcRrh5yDDQNFJ-lULWMcCEDVUCzYqYpM3Mb7","e":"AQAB","p":"jwSHtfq1lRYzXwEocW0EbbvJqiT7oneiBzH7Qs8evtCq9NwG","q":"cdhw0Fi-Np_gtAtxKSBxkxmOMjbjkc_JG0tMHMQ7_BXRki2N","dp":"rlILC4Ms3ShkiTmj5Vd55-g7f0tGikhNjLYOi5kkHYsgjtj0","dq":"Zi76xGV9UkUKpLRVrksM2P5xL6Wi-aqwu1m-a3EfMmwEN70R"};
void importJWK(key3, 'RS256');
