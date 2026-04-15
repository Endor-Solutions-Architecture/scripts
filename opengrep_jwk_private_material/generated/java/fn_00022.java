import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"cbydFOHB5yyb","alg":"RS256","n":"tOLNm68yhyNLNgN2CBciy-TO3CgoYxBJdwISbcbsagit8XLF","e":"AQAB"}
    String jwk = "{\"kty\":\"RSA\",\"kid\":\"cbydFOHB5yyb\",\"alg\":\"RS256\",\"n\":\"tOLNm68yhyNLNgN2CBciy-TO3CgoYxBJdwISbcbsagit8XLF\",\"e\":\"AQAB\"}";
    JWK.parse(jwk);
  }
}
