import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"SoJq_71MJ282","alg":"RS256","n":"e3hdB6MMd2aPS06OD-Q7RhT-ZzyGfqtxOtOvo9J3cvYShj1J","e":"AQAB"}
    String jwk = "{\"kty\":\"RSA\",\"kid\":\"SoJq_71MJ282\",\"alg\":\"RS256\",\"n\":\"e3hdB6MMd2aPS06OD-Q7RhT-ZzyGfqtxOtOvo9J3cvYShj1J\",\"e\":\"AQAB\"}";
    JWK.parse(jwk);
  }
}
