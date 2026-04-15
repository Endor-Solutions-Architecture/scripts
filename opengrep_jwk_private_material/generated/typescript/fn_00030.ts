import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"mdKyi_PiZrs6","alg":"RS256","n":"xzAqXb_fplewkvRYQUitQB8WZ5INkl4sFejUpSoK7CTTlpiQ","e":"AQAB"}
const key30: any = {"kty":"RSA","kid":"mdKyi_PiZrs6","alg":"RS256","n":"xzAqXb_fplewkvRYQUitQB8WZ5INkl4sFejUpSoK7CTTlpiQ","e":"AQAB"};
void importJWK(key30, 'RS256');
