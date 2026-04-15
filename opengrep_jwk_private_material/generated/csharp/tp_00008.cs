using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"ljwi8dyb437s","alg":"RS256","n":"8tyezmvQtZK6BDl688tzGon_nRR5onXBfLpPdGea3ck_wtpI","e":"AQAB","p":"xBTGmNTs_KQ6vhA46uffF9kHrafgHJKhv6d4MeVhh2qzrOSp","q":"QyA4AgcpX7hgQx00Y0s4UCnvdjh-3uOA-K6IjZdLaqEEuKoR","dp":"zw0u-QedGMRWl65y0bQaEJ2fqaELVr7csiRAkJ1LuGXPpoIn","dq":"pNHKxlJLFMq1MuF0ozLs7fRKZYyi8PMDwa6zlYlWdFbgZwOo"}
    var jwk = "{\"kty\":\"RSA\",\"kid\":\"ljwi8dyb437s\",\"alg\":\"RS256\",\"n\":\"8tyezmvQtZK6BDl688tzGon_nRR5onXBfLpPdGea3ck_wtpI\",\"e\":\"AQAB\",\"p\":\"xBTGmNTs_KQ6vhA46uffF9kHrafgHJKhv6d4MeVhh2qzrOSp\",\"q\":\"QyA4AgcpX7hgQx00Y0s4UCnvdjh-3uOA-K6IjZdLaqEEuKoR\",\"dp\":\"zw0u-QedGMRWl65y0bQaEJ2fqaELVr7csiRAkJ1LuGXPpoIn\",\"dq\":\"pNHKxlJLFMq1MuF0ozLs7fRKZYyi8PMDwa6zlYlWdFbgZwOo\"}";
    var key = new JsonWebKey(jwk);
  }
}
