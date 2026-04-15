import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"2Br4V2MkD23n","alg":"RS256","n":"UI_0yB7iI_6v1Feb8lYBmtdndWfXQk8lt3Q-cdUE9z3Sywwe","e":"AQAB"}
    String jwk = "{\"kty\":\"RSA\",\"kid\":\"2Br4V2MkD23n\",\"alg\":\"RS256\",\"n\":\"UI_0yB7iI_6v1Feb8lYBmtdndWfXQk8lt3Q-cdUE9z3Sywwe\",\"e\":\"AQAB\"}";
    JWK.parse(jwk);
  }
}
