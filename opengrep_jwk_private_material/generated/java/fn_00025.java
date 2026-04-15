import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"eBiHdRiN2FO1","alg":"RS256","n":"sKnjoEjShVnGkfZAipXuFwnEoYvpy_LcGi0STYr4fS19NNc2","e":"AQAB"}
    String jwk = "{\"kty\":\"RSA\",\"kid\":\"eBiHdRiN2FO1\",\"alg\":\"RS256\",\"n\":\"sKnjoEjShVnGkfZAipXuFwnEoYvpy_LcGi0STYr4fS19NNc2\",\"e\":\"AQAB\"}";
    JWK.parse(jwk);
  }
}
