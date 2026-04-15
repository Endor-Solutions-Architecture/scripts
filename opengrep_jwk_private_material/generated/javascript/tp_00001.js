import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"EC","kid":"sbfgGoqrvop9","alg":"ES256","crv":"P-256","x":"LizwK-0wQcWR46FVZF83LE43trCIDb16Tn3Tox-DY9m","y":"rwhKsVWaFZJ8uaZ6gqe7V6bWSFP8G48AOW_GfjAsxcM","d":"bjHlv7wFPAhp4acE1cc2IfMYwbytkhAGwyWesP5icP_FTK2n7yZiZ_mrbdLdibE7"}
const key1 = {"kty":"EC","kid":"sbfgGoqrvop9","alg":"ES256","crv":"P-256","x":"LizwK-0wQcWR46FVZF83LE43trCIDb16Tn3Tox-DY9m","y":"rwhKsVWaFZJ8uaZ6gqe7V6bWSFP8G48AOW_GfjAsxcM","d":"bjHlv7wFPAhp4acE1cc2IfMYwbytkhAGwyWesP5icP_FTK2n7yZiZ_mrbdLdibE7"};
void importJWK(key1, 'ES256');
