using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"OWIIuozE5N-c","alg":"RS256","n":"ooWo5I68_XxOmVsrcdsyeSj1BjhSUGVqnw7w5gtFMXlo4Akb","e":"AQAB"}
    var jwk = "{\"kty\":\"RSA\",\"kid\":\"OWIIuozE5N-c\",\"alg\":\"RS256\",\"n\":\"ooWo5I68_XxOmVsrcdsyeSj1BjhSUGVqnw7w5gtFMXlo4Akb\",\"e\":\"AQAB\"}";
    var key = new JsonWebKey(jwk);
  }
}
