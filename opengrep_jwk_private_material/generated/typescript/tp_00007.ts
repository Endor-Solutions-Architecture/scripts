import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"oct","kid":"pA58Gh4kSYVl","alg":"HS256","k":"5t1ybkBfNzSoSng-I3nHh2q0CDedE34UM-0FXOtlVmurlOWmNuxf6MUtkQLQVxmd"}
const key7: any = {"kty":"oct","kid":"pA58Gh4kSYVl","alg":"HS256","k":"5t1ybkBfNzSoSng-I3nHh2q0CDedE34UM-0FXOtlVmurlOWmNuxf6MUtkQLQVxmd"};
void importJWK(key7, 'HS256');
