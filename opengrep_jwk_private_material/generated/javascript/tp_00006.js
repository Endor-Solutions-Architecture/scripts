import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"EC","kid":"W8oKkJU3sgUW","alg":"ES256","crv":"P-256","x":"VpwNl9NXXhrCPbFfc1e8iJvGbM9QGlLUyPoecCgh07b","y":"rxshuYXGCAEI4Z7ottFkMq3VO59KN588t-OX66Ak3OE","d":"lK88Xx3K6lz40PZ6zuzsy1D2OH8SPoaRP-LJWFPo270k23VLZ5Zw8Qqa8NXtR_l0"}
const key6 = {"kty":"EC","kid":"W8oKkJU3sgUW","alg":"ES256","crv":"P-256","x":"VpwNl9NXXhrCPbFfc1e8iJvGbM9QGlLUyPoecCgh07b","y":"rxshuYXGCAEI4Z7ottFkMq3VO59KN588t-OX66Ak3OE","d":"lK88Xx3K6lz40PZ6zuzsy1D2OH8SPoaRP-LJWFPo270k23VLZ5Zw8Qqa8NXtR_l0"};
void importJWK(key6, 'ES256');
