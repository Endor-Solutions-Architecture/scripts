import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"oct","kid":"missing-k","alg":"HS256"}
    String jwk = "{\"kty\":\"oct\",\"kid\":\"missing-k\",\"alg\":\"HS256\"}";
    JWK.parse(jwk);
  }
}
