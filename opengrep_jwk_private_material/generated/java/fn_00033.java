import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"QJCdEyatFP5n","alg":"RS256","n":"Shv6XxtxdjL4l2XVRCkdhcGoqObU5ySp51Tq_YxF96z2KVdI","e":"AQAB"}
    String jwk = "{\"kty\":\"RSA\",\"kid\":\"QJCdEyatFP5n\",\"alg\":\"RS256\",\"n\":\"Shv6XxtxdjL4l2XVRCkdhcGoqObU5ySp51Tq_YxF96z2KVdI\",\"e\":\"AQAB\"}";
    JWK.parse(jwk);
  }
}
