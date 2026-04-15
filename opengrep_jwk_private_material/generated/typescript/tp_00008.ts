import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"Kk08rKWWEdUR","alg":"RS256","n":"-ueCpcBhAmo0hP_nPrYJqa5BlVALz7Too-lCmST5o-VcnzUD","e":"AQAB","p":"GFRl-spHeFrUm-KLJqBRQ-V_XqfGnqnw2lUCtjAWCbRLO3JF","q":"_8YNW0LrXyZMUwtxiql9SUEQlp5lBfDU1mmcgTsW0nuj6av2","dp":"qsCo7f5coqbbs5MQEWbgkfidSIbskZ1ka9zPM0MRX438ZWIS","dq":"bnaKUgUk_TIkQ9A78gQmbztdWv2YQRHX5DOeWUGW00n50Y0H"}
const key8: any = {"kty":"RSA","kid":"Kk08rKWWEdUR","alg":"RS256","n":"-ueCpcBhAmo0hP_nPrYJqa5BlVALz7Too-lCmST5o-VcnzUD","e":"AQAB","p":"GFRl-spHeFrUm-KLJqBRQ-V_XqfGnqnw2lUCtjAWCbRLO3JF","q":"_8YNW0LrXyZMUwtxiql9SUEQlp5lBfDU1mmcgTsW0nuj6av2","dp":"qsCo7f5coqbbs5MQEWbgkfidSIbskZ1ka9zPM0MRX438ZWIS","dq":"bnaKUgUk_TIkQ9A78gQmbztdWv2YQRHX5DOeWUGW00n50Y0H"};
void importJWK(key8, 'RS256');
