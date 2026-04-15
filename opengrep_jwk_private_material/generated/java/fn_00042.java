import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"RSy51Ibto6y1","alg":"RS256","n":"r6P3Px0Ox6wiWCVd_9H1vMiIeOZ5M1lXYOHbn9trWEwTHjpk","e":"AQAB"}
    String jwk = "{\"kty\":\"RSA\",\"kid\":\"RSy51Ibto6y1\",\"alg\":\"RS256\",\"n\":\"r6P3Px0Ox6wiWCVd_9H1vMiIeOZ5M1lXYOHbn9trWEwTHjpk\",\"e\":\"AQAB\"}";
    JWK.parse(jwk);
  }
}
