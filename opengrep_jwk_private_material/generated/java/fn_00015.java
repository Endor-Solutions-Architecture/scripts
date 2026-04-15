import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"8GJm-denCmJN","alg":"RS256","n":"dMYaFl6Ns6c5ThlwYMma4RH9Y0RjRvKU5Xk5hq54ugxvxjis","e":"AQAB"}
    String jwk = "{\"kty\":\"RSA\",\"kid\":\"8GJm-denCmJN\",\"alg\":\"RS256\",\"n\":\"dMYaFl6Ns6c5ThlwYMma4RH9Y0RjRvKU5Xk5hq54ugxvxjis\",\"e\":\"AQAB\"}";
    JWK.parse(jwk);
  }
}
