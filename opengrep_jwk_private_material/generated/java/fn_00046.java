import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"x1I8OUQK3Irx","alg":"RS256","n":"kgDzGXImX0XQxnjg6yqEGAZT-jiSY6yIfxi8tGSIsEJxCaW2","e":"AQAB"}
    String jwk = "{\"kty\":\"RSA\",\"kid\":\"x1I8OUQK3Irx\",\"alg\":\"RS256\",\"n\":\"kgDzGXImX0XQxnjg6yqEGAZT-jiSY6yIfxi8tGSIsEJxCaW2\",\"e\":\"AQAB\"}";
    JWK.parse(jwk);
  }
}
