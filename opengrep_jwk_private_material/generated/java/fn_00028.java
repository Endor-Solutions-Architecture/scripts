import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"3qrQQ2T8slLO","alg":"RS256","n":"qxGlO2tU65D5EXlXRA_vimAcOgyA0qPw2_7Mq_QtwIE-xkrd","e":"AQAB"}
    String jwk = "{\"kty\":\"RSA\",\"kid\":\"3qrQQ2T8slLO\",\"alg\":\"RS256\",\"n\":\"qxGlO2tU65D5EXlXRA_vimAcOgyA0qPw2_7Mq_QtwIE-xkrd\",\"e\":\"AQAB\"}";
    JWK.parse(jwk);
  }
}
