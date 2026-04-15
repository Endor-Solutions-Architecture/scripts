import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"JhlbCtomhm0b","alg":"RS256","n":"WxWsfSC6OLsJE5UYoIUy_x9ssXsjzbRJTeU4E2qxBK5shrv4","e":"AQAB","d":"AqjOGu9bfELb52Mw-eCfM6sQsrZVI6F1-JbnRPiZ4NaA1dwcvK6dO740ehJ6zi7Q"}
    String jwk = "{\"kty\":\"RSA\",\"kid\":\"JhlbCtomhm0b\",\"alg\":\"RS256\",\"n\":\"WxWsfSC6OLsJE5UYoIUy_x9ssXsjzbRJTeU4E2qxBK5shrv4\",\"e\":\"AQAB\",\"d\":\"AqjOGu9bfELb52Mw-eCfM6sQsrZVI6F1-JbnRPiZ4NaA1dwcvK6dO740ehJ6zi7Q\"}";
    JWK.parse(jwk);
  }
}
