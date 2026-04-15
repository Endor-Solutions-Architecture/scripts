import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"ZJjkKGWqhKAH","alg":"RS256","n":"3S4YOUW1iczkRzIRhKE0zCmqVRblnizmVZ45cLSXT3a9vkGI","e":"AQAB","d":"AOVSHUR9"}
    String jwk = "{\"kty\":\"RSA\",\"kid\":\"ZJjkKGWqhKAH\",\"alg\":\"RS256\",\"n\":\"3S4YOUW1iczkRzIRhKE0zCmqVRblnizmVZ45cLSXT3a9vkGI\",\"e\":\"AQAB\",\"d\":\"AOVSHUR9\"}";
    JWK.parse(jwk);
  }
}
