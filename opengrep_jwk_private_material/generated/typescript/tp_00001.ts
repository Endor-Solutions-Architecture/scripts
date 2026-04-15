import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"EC","kid":"SvTBzH99UMc_","alg":"ES256","crv":"P-256","x":"FPzKl9u3_C59IVkieTyAXRLC_wusOOhQYbwR46Y6thg","y":"m0UJsVs919UvFHywxHRaNnA12CwXoKm7M7cgdZ4JowN","d":"BD9UZP8LBXKRALcJI91I0yeZWUJpb8VnTw-Kn-g31XV94fuECcKeLis9zwBnEWcT"}
const key1: any = {"kty":"EC","kid":"SvTBzH99UMc_","alg":"ES256","crv":"P-256","x":"FPzKl9u3_C59IVkieTyAXRLC_wusOOhQYbwR46Y6thg","y":"m0UJsVs919UvFHywxHRaNnA12CwXoKm7M7cgdZ4JowN","d":"BD9UZP8LBXKRALcJI91I0yeZWUJpb8VnTw-Kn-g31XV94fuECcKeLis9zwBnEWcT"};
void importJWK(key1, 'ES256');
