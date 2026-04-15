import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"xa4DR0Z88X8H","alg":"RS256","n":"aW59IOnNuOWcE3QVteWvIciUqJB6CI3q00kJuL-xtU5WyEFz","e":"AQAB","p":"8MkB20tH7_QIp0_EyO2QDG4VHLxVbvzIAEvGsAOrve9zSqQ4","q":"S07yOlzXWawtxfHVZ-P3dmzYFiaTQuz6xEX-xE1xbFntwLmk","dp":"lXtySecF3cAneNV_8JDzxZogDzFvk6OQurf-iWiTVvwgggbT","dq":"XgubvwSAePgC6ZoNVq1M8tLogSbXUTSGdto9zxDt7s6TBAMX"}
const key3: any = {"kty":"RSA","kid":"xa4DR0Z88X8H","alg":"RS256","n":"aW59IOnNuOWcE3QVteWvIciUqJB6CI3q00kJuL-xtU5WyEFz","e":"AQAB","p":"8MkB20tH7_QIp0_EyO2QDG4VHLxVbvzIAEvGsAOrve9zSqQ4","q":"S07yOlzXWawtxfHVZ-P3dmzYFiaTQuz6xEX-xE1xbFntwLmk","dp":"lXtySecF3cAneNV_8JDzxZogDzFvk6OQurf-iWiTVvwgggbT","dq":"XgubvwSAePgC6ZoNVq1M8tLogSbXUTSGdto9zxDt7s6TBAMX"};
void importJWK(key3, 'RS256');
